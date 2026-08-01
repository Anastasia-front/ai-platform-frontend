import { test, expect } from "../fixtures/base";
import { uniqueName } from "../helpers/test-data";

test.describe("Account and session security @critical", () => {
  test("invalid bearer token is rejected by the backend", async ({ request }) => {
    const apiUrl = process.env.E2E_API_URL || "http://localhost:8000";
    const res = await request.get(`${apiUrl}/auth/me`, {
      headers: { Authorization: "Bearer not-a-real-token" },
    });
    expect(res.status()).toBe(401);
  });

  test("missing authentication is rejected on a protected backend route", async ({ request }) => {
    const apiUrl = process.env.E2E_API_URL || "http://localhost:8000";
    const res = await request.get(`${apiUrl}/projects/`);
    expect(res.status()).toBe(401);
  });

  test("resource IDs belonging to another user return 403/404, not the resource @critical", async ({
    primaryApi,
    secondaryApi,
  }, testInfo) => {
    const project = await secondaryApi.createProject(uniqueName("isolation-check", testInfo.workerIndex));
    const apiUrl = process.env.E2E_API_URL || "http://localhost:8000";

    const getRes = await primaryApi.raw().get(`${apiUrl}/projects/${project.id}`, {
      headers: primaryApi.authHeader(),
    });
    expect([403, 404]).toContain(getRes.status());

    const deleteRes = await primaryApi.raw().delete(`${apiUrl}/projects/${project.id}`, {
      headers: primaryApi.authHeader(),
    });
    expect([403, 404]).toContain(deleteRes.status());

    await secondaryApi.deleteProject(project.id);
  });

  test("server-side validation rejects an invalid project payload even if the UI is bypassed", async ({
    primaryApi,
  }) => {
    const apiUrl = process.env.E2E_API_URL || "http://localhost:8000";
    // `name` is a required field on ProjectCreate (app/schemas/project.py) —
    // omitting it entirely is rejected by pydantic regardless of what the
    // Django form does. (An empty string "" is currently accepted by the
    // API — see tests/api/projects/projects.spec.ts and TEST_PLAN.md.)
    const res = await primaryApi.raw().post(`${apiUrl}/projects/`, {
      headers: primaryApi.authHeader(),
      data: {},
    });
    expect(res.status()).toBe(422);
  });

  test("no sensitive values leak into rendered HTML on the projects page @regression", async ({
    page,
  }) => {
    await page.goto("/projects/");
    const html = await page.content();
    expect(html).not.toMatch(/Bearer\s+[A-Za-z0-9\-._~+/]+=*/);
    expect(html.toLowerCase()).not.toContain("password");
  });

  test("open redirect via next= is prevented @regression", async ({ page }) => {
    await page.goto("/logout/");
    await page.goto("/login/?next=https://evil.example.com");
    const { env } = await import("../helpers/env");
    await page.getByLabel("Email").fill(env.userEmail());
    await page.getByLabel("Password", { exact: true }).fill(env.userPassword());
    await page.getByRole("button", { name: "Log in" }).click();
    // An absolute external `next` must never be honored as a redirect target.
    await expect(page).not.toHaveURL(/evil\.example\.com/);
  });
});
