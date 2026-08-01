import { expect, test } from "../fixtures/base";

test.use({ storageState: { cookies: [], origins: [] } });

test.describe("Public pages and navigation", () => {
  test("homepage loads successfully @smoke @critical @production-safe", async ({
    page,
  }) => {
    const res = await page.goto("/");
    expect(res?.status(), "homepage should not error").toBeLessThan(400);
    await expect(page).toHaveTitle(/.+/);
  });

  test("login page loads with expected content @smoke @critical @production-safe", async ({
    page,
  }) => {
    await page.goto("/login/");
    await expect(page.getByRole("heading", { name: "Log in" })).toBeVisible();
    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(page.getByLabel("Password", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Log in" })).toBeVisible();
  });

  test("register page loads with expected content @smoke @critical @production-safe", async ({
    page,
  }) => {
    await page.goto("/register/");
    await expect(page.getByRole("button", { name: /register/i })).toBeVisible();
  });

  test("favicon returns successfully @smoke @production-safe", async ({
    page,
  }) => {
    const res = await page.goto("/favicon.ico");
    expect(res?.status()).toBeLessThan(400);
  });

  test("unsupported route produces a 404 @regression @production-safe", async ({
    page,
  }) => {
    const res = await page.goto("/this-route-does-not-exist-e2e/");
    expect(res?.status()).toBe(404);
  });

  test("unauthenticated access to protected pages redirects to login @critical @production-safe", async ({
    page,
  }) => {
    await page.goto("/projects/");
    await expect(page).toHaveURL(/\/login\//);
  });

  test("login-to-register and back navigation works @regression @production-safe", async ({
    page,
  }) => {
    await page.goto("/login/");
    await page.getByRole("link", { name: "Register" }).click();
    await expect(page).toHaveURL(/\/register\//);
  });
});

test.describe("Health and diagnostics @production-safe", () => {
  test("frontend health endpoint responds @smoke @critical", async ({
    request,
    baseURL,
  }) => {
    const res = await request.get(`${baseURL}/health/`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.status).toBe("ok");
  });

  test("backend health endpoint responds @smoke @critical", async ({
    request,
  }) => {
    const apiUrl = process.env.E2E_API_URL || "http://localhost:8000";
    const res = await request.get(`${apiUrl}/health`);
    expect(res.ok()).toBeTruthy();
  });
});

test.describe("Console and network cleanliness", () => {
  test("homepage has no unexpected console errors or 5xx requests @regression @production-safe", async ({
    page,
    diagnostics,
  }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    expect(diagnostics.consoleErrors).toEqual([]);
    expect(diagnostics.failedRequests).toEqual([]);
  });
});
