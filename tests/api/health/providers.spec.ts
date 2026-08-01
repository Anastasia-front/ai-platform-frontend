import { test, expect } from "@playwright/test";
import { BackendApiClient } from "../../e2e/helpers/api-client";
import { env } from "../../e2e/helpers/env";

const apiUrl = process.env.E2E_API_URL || "http://localhost:8000";

test.describe("Providers API @api @regression", () => {
  let api: BackendApiClient;

  test.beforeAll(async () => {
    api = await BackendApiClient.login(env.userEmail(), env.userPassword());
  });
  test.afterAll(async () => {
    await api.dispose();
  });

  test("provider list is returned and never includes a raw api key", async () => {
    const res = await api.raw().get(`${apiUrl}/providers`, { headers: api.authHeader() });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const serialized = JSON.stringify(body);
    expect(serialized).not.toMatch(/sk-[a-zA-Z0-9]{20,}/);
  });

  test("provider config endpoint responds", async () => {
    const res = await api.raw().get(`${apiUrl}/providers/config`, { headers: api.authHeader() });
    expect(res.ok()).toBeTruthy();
  });

  test("missing auth on providers list returns 401", async () => {
    const res = await api.raw().get(`${apiUrl}/providers`);
    expect(res.status()).toBe(401);
  });
});
