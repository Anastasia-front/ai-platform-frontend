import { test, expect } from "../fixtures/base";
import { env, allowProductionSmokeWrites } from "../helpers/env";

/**
 * Strictly non-destructive checks. Every test here is tagged
 * @production-safe and must never write, delete, or mutate real data.
 * These are the only tests the post-deployment CI job runs (see
 * .github/workflows/e2e-prod-smoke.yml).
 */
test.describe("Production smoke @production-safe", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("public homepage returns successfully @smoke @critical", async ({ page }) => {
    const res = await page.goto("/");
    expect(res?.status()).toBeLessThan(400);
  });

  test("static assets and favicon load @smoke", async ({ page }) => {
    const res = await page.goto("/favicon.ico");
    expect(res?.status()).toBeLessThan(400);
  });

  test("login page renders @smoke @critical", async ({ page }) => {
    await page.goto("/login/");
    await expect(page.getByRole("heading", { name: "Log in" })).toBeVisible();
  });

  test("frontend health endpoint responds @smoke @critical", async ({ request, baseURL }) => {
    const res = await request.get(`${baseURL}/health/`);
    expect(res.ok()).toBeTruthy();
  });

  test("backend health endpoint responds @smoke @critical", async ({ request }) => {
    const apiUrl = process.env.E2E_API_URL;
    if (!apiUrl) test.skip(true, "E2E_API_URL not set for this smoke run");
    const res = await request.get(`${apiUrl}/health`);
    expect(res.ok()).toBeTruthy();
  });

  test("dedicated smoke account can log in and see the dashboard @smoke @critical", async ({
    page,
    diagnostics,
  }) => {
    await page.goto("/login/");
    await page.getByLabel("Email").fill(env.prodSmokeEmail());
    await page.getByLabel("Password", { exact: true }).fill(env.prodSmokePassword());
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page).toHaveURL(/\/projects\//);
    expect(diagnostics.consoleErrors).toEqual([]);
    expect(diagnostics.failedRequests).toEqual([]);
  });

  test("read-only navigation to projects list works @smoke", async ({ page }) => {
    await page.goto("/login/");
    await page.getByLabel("Email").fill(env.prodSmokeEmail());
    await page.getByLabel("Password", { exact: true }).fill(env.prodSmokePassword());
    await page.getByRole("button", { name: "Log in" }).click();
    await page.goto("/projects/");
    await expect(page.locator("body")).not.toContainText(/traceback|internal server error/i);
  });

  test("logout works @smoke @critical", async ({ page }) => {
    await page.goto("/login/");
    await page.getByLabel("Email").fill(env.prodSmokeEmail());
    await page.getByLabel("Password", { exact: true }).fill(env.prodSmokePassword());
    await page.getByRole("button", { name: "Log in" }).click();
    await page.goto("/logout/");
    await expect(page).toHaveURL(/\/login\//);
    await page.goto("/projects/");
    await expect(page).toHaveURL(/\/login\//);
  });
});

test.describe("Production smoke — opt-in controlled writes @production-safe", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("prod-smoke-prefixed project can be created and cleaned up", async ({ page }) => {
    test.skip(!allowProductionSmokeWrites(), "ALLOW_PRODUCTION_SMOKE_WRITES is not enabled");

    const name = `prod-smoke-${Date.now()}`;
    await page.goto("/login/");
    await page.getByLabel("Email").fill(env.prodSmokeEmail());
    await page.getByLabel("Password", { exact: true }).fill(env.prodSmokePassword());
    await page.getByRole("button", { name: "Log in" }).click();

    await page.goto("/projects/new/");
    await page.getByLabel("Name").fill(name);
    await page.getByRole("button", { name: "Create Project" }).click();
    await expect(page).toHaveURL(/\/projects\/[^/]+\/$/);

    // Clean up immediately — this suite must never leave prod-smoke-* data behind.
    await page.getByText("Delete Project").click();
    await expect(page).toHaveURL(/\/projects\/$/);
    await expect(page.getByText(name)).toHaveCount(0);
  });
});
