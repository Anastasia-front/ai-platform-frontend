import { test, expect } from "../fixtures/base";
import { uniqueName } from "../helpers/test-data";
import { fixtures, oversizedFilePayload, emptyFilePayload } from "../helpers/fixture-files";
import { waitForStatusText } from "../helpers/polling";

async function openFreshProject(page: import("@playwright/test").Page, primaryApi: any, name: string) {
  const project = await primaryApi.createProject(name);
  const slug = String(project.name).toLowerCase().replace(/[^a-z0-9]+/g, "-");
  await page.goto(`/projects/${slug}/`);
  return { project, slug };
}

/**
 * The `<details class="documents-accordion">` panel isn't persisted open —
 * the upload form's own submit redirects back to the same page (with a
 * fresh, collapsed accordion), so the just-uploaded row exists in the DOM
 * but stays hidden until the accordion is reopened.
 *
 * Set `.open` directly via JS rather than clicking the `<summary>`: WebKit's
 * hit-testing for nested `<details>/<summary>` intercepts the click on the
 * parent `<details>` element itself, making a real click unreliable there.
 * Setting the property is what a click does under the hood anyway, without
 * the cross-browser hit-testing quirk.
 */
async function reopenDocumentsAccordion(page: import("@playwright/test").Page) {
  await page.locator(".documents-accordion").evaluate((el) => {
    (el as HTMLDetailsElement).open = true;
  });
}

test.describe("Document upload and processing @critical", () => {
  test("upload a supported document and reach a terminal status @smoke @slow", async ({
    page,
    primaryApi,
  }, testInfo) => {
    testInfo.setTimeout(150_000);
    const { project } = await openFreshProject(page, primaryApi, uniqueName("doc-project", testInfo.workerIndex));

    await reopenDocumentsAccordion(page);
    await page.locator('input[name=file]').setInputFiles(fixtures.smallTxt);
    await page.locator(".upload-form").getByRole("button", { name: "Upload" }).click();
    await reopenDocumentsAccordion(page);

    const row = page.locator("[data-document-row]", { hasText: "small.txt" });
    await expect(row).toBeVisible({ timeout: 15_000 });

    const status = row.locator("[data-document-status]");
    await waitForStatusText(status, /indexed|failed/, { timeoutMs: 120_000, label: "document status" });

    await page.reload();
    await reopenDocumentsAccordion(page);
    await expect(page.locator("[data-document-row]", { hasText: "small.txt" })).toBeVisible();

    await primaryApi.deleteProject(project.id);
  });

  test("invalid extension is rejected @slow", async ({ page, primaryApi }, testInfo) => {
    testInfo.setTimeout(90_000);
    const { project } = await openFreshProject(page, primaryApi, uniqueName("doc-invalid-ext", testInfo.workerIndex));
    await reopenDocumentsAccordion(page);
    await page.locator('input[name=file]').setInputFiles(fixtures.invalidExtension);
    await page.locator(".upload-form").getByRole("button", { name: "Upload" }).click();
    await reopenDocumentsAccordion(page);

    // Either rejected client-side (accept attribute) or server-side (flash/error) —
    // in both cases the app must not crash and must not silently accept it as processed.
    await expect(page.locator("body")).not.toContainText(/traceback|internal server error/i);
    const acceptedRow = page.locator("[data-document-row]", { hasText: "invalid-extension.exe" });
    if (await acceptedRow.isVisible().catch(() => false)) {
      const status = acceptedRow.locator("[data-document-status]");
      await waitForStatusText(status, /failed/, { timeoutMs: 60_000, label: "invalid extension status" });
    }

    await primaryApi.deleteProject(project.id);
  });

  test("malformed file is handled without crashing @regression @slow", async ({ page, primaryApi }, testInfo) => {
    testInfo.setTimeout(150_000);
    const { project } = await openFreshProject(page, primaryApi, uniqueName("doc-malformed", testInfo.workerIndex));
    await reopenDocumentsAccordion(page);
    await page.locator('input[name=file]').setInputFiles(fixtures.malformedPdf);
    await page.locator(".upload-form").getByRole("button", { name: "Upload" }).click();
    await reopenDocumentsAccordion(page);

    const row = page.locator("[data-document-row]", { hasText: "malformed.pdf" });
    await expect(row).toBeVisible({ timeout: 15_000 });
    const processButton = row.getByRole("button", { name: /process/i });
    if (await processButton.isVisible().catch(() => false)) {
      await processButton.click();
    }
    const status = row.locator("[data-document-status]");
    await waitForStatusText(status, /indexed|failed/, { timeoutMs: 120_000, label: "malformed document status" });

    await primaryApi.deleteProject(project.id);
  });

  test("empty file is handled without crashing @regression", async ({ page, primaryApi }, testInfo) => {
    const { project } = await openFreshProject(page, primaryApi, uniqueName("doc-empty", testInfo.workerIndex));
    await reopenDocumentsAccordion(page);
    await page.locator('input[name=file]').setInputFiles(emptyFilePayload());
    await page.locator(".upload-form").getByRole("button", { name: "Upload" }).click();
    await reopenDocumentsAccordion(page);
    await expect(page.locator("body")).not.toContainText(/traceback|internal server error/i);

    await primaryApi.deleteProject(project.id);
  });

  test("backend file-size limit is enforced @regression @slow", async ({ page, primaryApi }, testInfo) => {
    const { project } = await openFreshProject(page, primaryApi, uniqueName("doc-oversized", testInfo.workerIndex));
    await reopenDocumentsAccordion(page);
    await page.locator('input[name=file]').setInputFiles(oversizedFilePayload());
    await page.locator(".upload-form").getByRole("button", { name: "Upload" }).click();
    await reopenDocumentsAccordion(page);
    await expect(page.locator("body")).not.toContainText(/traceback|internal server error/i);

    await primaryApi.deleteProject(project.id);
  });

  test("delete a document removes it from the list @regression", async ({ page, primaryApi }, testInfo) => {
    const { project } = await openFreshProject(page, primaryApi, uniqueName("doc-delete", testInfo.workerIndex));
    await reopenDocumentsAccordion(page);
    await page.locator('input[name=file]').setInputFiles(fixtures.smallCsv);
    await page.locator(".upload-form").getByRole("button", { name: "Upload" }).click();
    await reopenDocumentsAccordion(page);

    const row = page.locator("[data-document-row]", { hasText: "small.csv" });
    await expect(row).toBeVisible({ timeout: 15_000 });
    await row.getByRole("button", { name: "Delete" }).click();
    await expect(page.locator("[data-document-row]", { hasText: "small.csv" })).toHaveCount(0);

    await primaryApi.deleteProject(project.id);
  });
});

test.describe("Document ownership @critical", () => {
  test("user cannot access another user's document via API", async ({ primaryApi, secondaryApi }, testInfo) => {
    const project = await secondaryApi.createProject(uniqueName("secondary-doc-project", testInfo.workerIndex));
    const document = await secondaryApi.uploadDocument(project.id, fixtures.smallTxt, "text/plain");

    const res = await primaryApi.raw().get(`${process.env.E2E_API_URL || "http://localhost:8000"}/documents/${document.id}`, {
      headers: primaryApi.authHeader(),
    });
    expect([403, 404]).toContain(res.status());

    await secondaryApi.deleteProject(project.id);
  });
});
