import { test, expect } from "@playwright/test";

const apiUrl = process.env.E2E_API_URL || "http://localhost:8000";

test.describe("Backend health @api @smoke @critical @production-safe", () => {
  test("GET /health responds successfully", async ({ request }) => {
    const res = await request.get(`${apiUrl}/health`);
    expect(res.ok()).toBeTruthy();
    expect(res.headers()["content-type"]).toContain("application/json");
  });

  test("GET /openapi.json is served", async ({ request }) => {
    const res = await request.get(`${apiUrl}/openapi.json`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.openapi).toBeTruthy();
    expect(body.paths).toBeTruthy();
  });
});
