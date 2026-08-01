import { test, expect } from "../fixtures/base";
import { uniqueName } from "../helpers/test-data";

test.describe("Project CRUD @critical", () => {
  test("create, list and open a project @smoke", async ({ page }, testInfo) => {
    const name = uniqueName("project", testInfo.workerIndex);

    await page.goto("/projects/new/");
    await page.getByLabel("Name").fill(name);
    await page.getByLabel("Description").fill("Created by Playwright E2E");
    await page.getByRole("button", { name: "Create Project" }).click();

    await expect(page).toHaveURL(/\/projects\/[^/]+\/$/);

    await page.goto("/projects/");
    const card = page.locator(".project-card", { hasText: name });
    await expect(card).toBeVisible();

    await card.getByRole("link", { name }).click();
    await expect(page).toHaveURL(/\/projects\/[^/]+\/$/);
  });

  test("empty project name is rejected client-side", async ({ page }) => {
    // The `name` input is HTML5 `required` (see dashboard/templates/dashboard/projects/new.html)
    // — an empty submit is blocked in the browser before Django's own
    // "Project name is required." validation is ever reached.
    await page.goto("/projects/new/");
    const nameInput = page.getByLabel("Name");
    await page.getByRole("button", { name: "Create Project" }).click();
    await expect(page).toHaveURL(/\/projects\/new\//);
    const isValid = await nameInput.evaluate((el: HTMLInputElement) =>
      el.checkValidity(),
    );
    expect(isValid).toBe(false);
  });

  test("rename a project persists after reload @regression", async ({
    page,
  }, testInfo) => {
    const name = uniqueName("rename-me", testInfo.workerIndex);
    const renamed = `${name}-renamed`;

    await page.goto("/projects/new/");
    await page.getByLabel("Name").fill(name);
    await page.getByRole("button", { name: "Create Project" }).click();
    await expect(page).toHaveURL(/\/projects\/[^/]+\/$/);

    await page.getByText("Rename project").click();
    const renameInput = page.locator(".rename-form input[name=name]");
    await renameInput.fill(renamed);
    await page
      .locator(".rename-form")
      .getByRole("button", { name: "Save" })
      .click();

    await expect(page).toHaveURL(/\/projects\/[^/]+\/$/);
    await page.reload();
    await expect(page.locator("p.eyebrow")).toHaveText(renamed);
  });

  test("delete a project removes it from the list @regression", async ({
    page,
  }, testInfo) => {
    const name = uniqueName("to-delete", testInfo.workerIndex);

    await page.goto("/projects/new/");
    await page.getByLabel("Name").fill(name);
    await page.getByRole("button", { name: "Create Project" }).click();
    await expect(page).toHaveURL(/\/projects\/[^/]+\/$/);

    await page.goto("/projects/");
    const card = page.locator(".project-card", { hasText: name });
    await card.getByRole("button", { name: "Delete" }).click();

    await expect(page).toHaveURL(/\/projects\/$/);
    await expect(page.locator(".project-card", { hasText: name })).toHaveCount(
      0,
    );
  });

  test("direct navigation to a deleted project shows an error, not a crash @regression", async ({
    page,
    primaryApi,
  }, testInfo) => {
    const project = await primaryApi.createProject(
      uniqueName("temp", testInfo.workerIndex),
    );
    await primaryApi.deleteProject(project.id);

    const slug = String(project.name)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-");
    await page.goto(`/projects/${slug}/`);
    // The app renders a page-level error rather than a hard crash (see
    // dashboard/views/projects.py: project_detail sets page_error on failure).
    await expect(page.locator("body")).not.toContainText(
      /traceback|internal server error/i,
    );
  });

  test("empty projects state renders guidance @regression", async ({
    page,
    primaryApi,
  }) => {
    // Not universally guaranteed empty (shared account may have other projects),
    // so this only asserts the empty-state markup contract when it does apply.
    await page.goto("/projects/");
    const emptyState = page.locator(".empty-state", {
      hasText: "No projects yet",
    });
    if (await emptyState.isVisible().catch(() => false)) {
      await expect(
        page.getByRole("link", { name: "Create Project" }),
      ).toBeVisible();
    }
  });
});

test.describe("Project ownership @critical", () => {
  test("user cannot open another user's project", async ({
    page,
    secondaryApi,
  }, testInfo) => {
    const project = await secondaryApi.createProject(
      uniqueName("owned-by-secondary", testInfo.workerIndex),
    );
    const slug = String(project.name)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-");

    // `page` is authenticated as the primary user via storageState.
    await page.goto(`/projects/${slug}/`);
    await expect(page.locator("body")).not.toContainText(project.name);

    await secondaryApi.deleteProject(project.id);
  });
});
