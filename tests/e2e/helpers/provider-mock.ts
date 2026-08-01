import { Page } from "@playwright/test";

/**
 * Frontend-level provider mocking.
 *
 * IMPORTANT limitation (see tests/e2e/README.md "Known gaps"): the actual AI
 * provider calls (Ollama/Gemini/OpenRouter/Groq) happen server-side inside
 * the FastAPI backend, not in the browser. Playwright's browser-level route
 * interception cannot intercept that outbound call.
 *
 * The chat composer (static/dashboard/chat.js) does NOT do a plain form
 * POST to `.../messages/send/` — it intercepts submit and does a
 * `fetch()` against `form.dataset.messageStreamUrl`
 * (`.../messages/stream/`), reading a text/event-stream (SSE) body frame by
 * frame via `parseSseFrames()`. Each frame is `event: <name>\ndata: <json>\n\n`
 * and a terminal frame's event must be one of completed/failed/cancelled.
 * These helpers mock that exact wire format.
 */
function sseFrame(event: string, data: Record<string, unknown>): string {
  return `event: ${event}\ndata: ${JSON.stringify({ event, ...data })}\n\n`;
}

export async function mockChatSend(page: Page, responseText = "This is a mocked AI response."): Promise<void> {
  await page.route("**/messages/stream/", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: sseFrame("completed", { content: responseText }),
    });
  });
}

export async function mockChatSendFailure(
  page: Page,
  errorMessage = "The AI provider is currently unavailable. Please try again."
): Promise<void> {
  await page.route("**/messages/stream/", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: sseFrame("failed", { error: errorMessage }),
    });
  });
}
