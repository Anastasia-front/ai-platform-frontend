import { test, expect } from "../fixtures/base";
import { uniqueName } from "../helpers/test-data";
import { mockChatSend, mockChatSendFailure } from "../helpers/provider-mock";

/**
 * These tests use the frontend-level provider mock (see helpers/provider-mock.ts).
 * They validate the Django rendering contract for chat send/error states
 * deterministically; they do not exercise the real backend -> LLM provider
 * call. See tests/e2e/README.md "Known gaps".
 */
test.describe("Chat flow @critical @mocked-frontend-only", () => {
  test("create a chat, send a message, see the response @smoke", async ({
    page,
    primaryApi,
  }, testInfo) => {
    const project = await primaryApi.createProject(uniqueName("chat-project", testInfo.workerIndex));
    const slug = String(project.name).toLowerCase().replace(/[^a-z0-9]+/g, "-");

    await page.goto(`/projects/${slug}/`);
    await page.getByPlaceholder("New chat title").fill("My first chat");
    await page.locator(".chat-create-form").getByRole("button", { name: "Create" }).click();

    await mockChatSend(page, "Mocked deterministic assistant reply.");
    await page.getByPlaceholder("Message the assistant...").fill("Hello, assistant.");
    await page.getByRole("button", { name: "Send" }).click();

    await expect(page.locator("#messages")).toContainText("Mocked deterministic assistant reply.");
    // No reload-persistence assertion here: the composer's real request is
    // intercepted client-side (see helpers/provider-mock.ts) before it ever
    // reaches Django/the backend, so neither the user message nor the reply
    // is actually saved — reloading would always show an empty chat.
    // Message-history persistence across reload needs a real (or backend-
    // mocked) provider round trip and is tracked as a gap in TEST_PLAN.md.

    await primaryApi.deleteProject(project.id);
  });

  test("empty message is rejected by the client", async ({ page, primaryApi }, testInfo) => {
    const project = await primaryApi.createProject(uniqueName("chat-empty", testInfo.workerIndex));
    const slug = String(project.name).toLowerCase().replace(/[^a-z0-9]+/g, "-");
    await page.goto(`/projects/${slug}/`);
    await page.locator(".chat-create-form").getByRole("button", { name: "Create" }).click();

    const textarea = page.getByPlaceholder("Message the assistant...");
    await page.getByRole("button", { name: "Send" }).click();
    const isValid = await textarea.evaluate((el: HTMLTextAreaElement) => el.checkValidity());
    expect(isValid).toBe(false);

    await primaryApi.deleteProject(project.id);
  });

  test("provider failure surfaces an error message, not a crash", async ({ page, primaryApi }, testInfo) => {
    const project = await primaryApi.createProject(uniqueName("chat-fail", testInfo.workerIndex));
    const slug = String(project.name).toLowerCase().replace(/[^a-z0-9]+/g, "-");
    await page.goto(`/projects/${slug}/`);
    await page.locator(".chat-create-form").getByRole("button", { name: "Create" }).click();

    await mockChatSendFailure(page);
    await page.getByPlaceholder("Message the assistant...").fill("Trigger a failure");
    await page.getByRole("button", { name: "Send" }).click();

    await expect(page.locator("body")).not.toContainText(/traceback|internal server error/i);
    await expect(page.getByText(/unavailable|try again/i)).toBeVisible();

    await primaryApi.deleteProject(project.id);
  });

  test("rapid double-submit does not create duplicate messages @regression", async ({
    page,
    primaryApi,
  }, testInfo) => {
    const project = await primaryApi.createProject(uniqueName("chat-double-submit", testInfo.workerIndex));
    const slug = String(project.name).toLowerCase().replace(/[^a-z0-9]+/g, "-");
    await page.goto(`/projects/${slug}/`);
    await page.locator(".chat-create-form").getByRole("button", { name: "Create" }).click();

    await mockChatSend(page, "Only one reply should render.");
    await page.getByPlaceholder("Message the assistant...").fill("Double-submit test message");

    const sendButton = page.getByRole("button", { name: "Send" });
    // Two clicks fired without awaiting between them, simulating a user
    // double-clicking before the composer disables itself.
    await Promise.all([sendButton.click(), sendButton.click()]);

    await expect(page.locator("#messages")).toContainText("Only one reply should render.");
    await expect(page.locator(".message.user")).toHaveCount(1);
    await expect(page.locator(".message.assistant")).toHaveCount(1);

    await primaryApi.deleteProject(project.id);
  });

  test("switching chats does not mix messages @regression", async ({
    page,
    primaryApi,
  }, testInfo) => {
    const project = await primaryApi.createProject(uniqueName("chat-switch", testInfo.workerIndex));
    const chatA = await primaryApi.createChat(project.id, "Chat A");
    const chatB = await primaryApi.createChat(project.id, "Chat B");
    const slug = String(project.name).toLowerCase().replace(/[^a-z0-9]+/g, "-");
    const chatASlug = "chat-a";
    const chatBSlug = "chat-b";

    await page.goto(`/projects/${slug}/chats/${chatASlug}/`);
    await expect(page.getByRole("heading", { name: "Chat A" })).toBeVisible();

    await page.goto(`/projects/${slug}/chats/${chatBSlug}/`);
    await expect(page.getByRole("heading", { name: "Chat B" })).toBeVisible();
    // Chat A's title must not still be showing once we've navigated to B.
    await expect(page.getByRole("heading", { name: "Chat A" })).toHaveCount(0);

    await primaryApi.deleteProject(project.id);
  });

  test("delete chat removes it from the conversation @regression", async ({ page, primaryApi }, testInfo) => {
    const project = await primaryApi.createProject(uniqueName("chat-delete", testInfo.workerIndex));
    const chat = await primaryApi.createChat(project.id, "To delete");
    const slug = String(project.name).toLowerCase().replace(/[^a-z0-9]+/g, "-");
    const chatSlug = String(chat.title ?? "to-delete").toLowerCase().replace(/[^a-z0-9]+/g, "-");

    await page.goto(`/projects/${slug}/chats/${chatSlug}/`);
    await page.getByRole("button", { name: "Delete Chat" }).click();
    await expect(page.getByRole("button", { name: "Delete Chat" })).toHaveCount(0);

    await primaryApi.deleteProject(project.id);
  });
});

test.describe("Chat ownership @critical", () => {
  test("user cannot open another user's chat", async ({ page, secondaryApi }, testInfo) => {
    const project = await secondaryApi.createProject(uniqueName("secondary-chat-project", testInfo.workerIndex));
    const chat = await secondaryApi.createChat(project.id, "Secondary's chat");
    const slug = String(project.name).toLowerCase().replace(/[^a-z0-9]+/g, "-");
    const chatSlug = String(chat.title).toLowerCase().replace(/[^a-z0-9]+/g, "-");

    await page.goto(`/projects/${slug}/chats/${chatSlug}/`);
    await expect(page.locator("body")).not.toContainText("Secondary's chat");

    await secondaryApi.deleteProject(project.id);
  });
});
