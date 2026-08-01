import { test, expect } from "../fixtures/base";
import { uniqueName } from "../helpers/test-data";
import { fixtures } from "../helpers/fixture-files";

/**
 * Verifies the actual HTMX polling wiring, not just the eventual UI state:
 * `dashboard/partials/document_status.html` only attaches
 * `hx-get`/`hx-trigger="every 3s"` while the document is in an active
 * processing status, and the template omits those attributes entirely once
 * a terminal status is reached. If polling never stopped, or never started,
 * a status assertion alone wouldn't catch either failure mode.
 */
test.describe("HTMX document status polling @regression @slow", () => {
  test("polling attributes appear while processing and disappear once terminal", async ({
    page,
    primaryApi,
  }, testInfo) => {
    testInfo.setTimeout(150_000);
    const project = await primaryApi.createProject(uniqueName("htmx-poll-project", testInfo.workerIndex));
    const slug = String(project.name).toLowerCase().replace(/[^a-z0-9]+/g, "-");
    await page.goto(`/projects/${slug}/`);

    const accordion = page.locator(".documents-accordion");
    await accordion.evaluate((el) => {
      (el as HTMLDetailsElement).open = true;
    });
    await page.locator('input[name=file]').setInputFiles(fixtures.smallTxt);
    await page.locator(".upload-form").getByRole("button", { name: "Upload" }).click();
    await accordion.evaluate((el) => {
      (el as HTMLDetailsElement).open = true;
    });

    const row = page.locator("[data-document-row]", { hasText: "small.txt" });
    await expect(row).toBeVisible({ timeout: 15_000 });
    const status = row.locator("[data-document-status]");

    // While still active (queued/processing/cancelling), the badge must
    // carry the polling attributes.
    const currentStatus = await status.evaluate((el) => el.dataset.documentId && el.textContent);
    if (/queued|processing/i.test(currentStatus ?? "")) {
      await expect(status).toHaveAttribute("hx-trigger", "every 3s");
      await expect(status).toHaveAttribute("hx-get", /.+/);
    }

    // Poll until a terminal status, then assert polling has stopped.
    await expect(async () => {
      const text = await status.textContent();
      expect(text).toMatch(/indexed|failed/);
    }).toPass({ timeout: 120_000, intervals: [2_000] });

    await expect(status).not.toHaveAttribute("hx-trigger", /.+/);
    await expect(status).not.toHaveAttribute("hx-get", /.+/);

    await primaryApi.deleteProject(project.id);
  });
});

test.describe("Browser back/forward after HTMX updates @regression", () => {
  test("back navigation after switching projects returns the previous project view", async ({
    page,
    primaryApi,
  }, testInfo) => {
    const projectA = await primaryApi.createProject(uniqueName("nav-project-a", testInfo.workerIndex));
    const projectB = await primaryApi.createProject(uniqueName("nav-project-b", testInfo.workerIndex));
    const slugA = String(projectA.name).toLowerCase().replace(/[^a-z0-9]+/g, "-");
    const slugB = String(projectB.name).toLowerCase().replace(/[^a-z0-9]+/g, "-");

    await page.goto(`/projects/${slugA}/`);
    await expect(page.locator("p.eyebrow")).toHaveText(projectA.name);

    await page.goto(`/projects/${slugB}/`);
    await expect(page.locator("p.eyebrow")).toHaveText(projectB.name);

    await page.goBack();
    await expect(page.locator("p.eyebrow")).toHaveText(projectA.name);

    await page.goForward();
    await expect(page.locator("p.eyebrow")).toHaveText(projectB.name);

    await primaryApi.deleteProject(projectA.id);
    await primaryApi.deleteProject(projectB.id);
  });
});
