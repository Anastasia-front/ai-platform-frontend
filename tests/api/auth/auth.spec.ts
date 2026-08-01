import { test, expect } from "@playwright/test";
import { env, runId } from "../../e2e/helpers/env";

const apiUrl = process.env.E2E_API_URL || "http://localhost:8000";

test.describe("Auth API @api @critical", () => {
  test("register + login + /auth/me round trip", async ({ request }, testInfo) => {
    const email = `${runId(testInfo.workerIndex)}@example.com`;
    const password = "Str0ng!Passw0rd";

    const registerRes = await request.post(`${apiUrl}/auth/register`, {
      data: { email, password },
    });
    expect(registerRes.status()).toBeGreaterThanOrEqual(200);
    expect(registerRes.status()).toBeLessThan(300);
    const registered = await registerRes.json();
    expect(registered.email).toBe(email);

    const loginRes = await request.post(`${apiUrl}/auth/login`, {
      form: { username: email, password },
    });
    expect(loginRes.ok()).toBeTruthy();
    const tokens = await loginRes.json();
    expect(tokens.access_token).toBeTruthy();
    expect(tokens.refresh_token).toBeTruthy();

    const meRes = await request.get(`${apiUrl}/auth/me`, {
      headers: { Authorization: `Bearer ${tokens.access_token}` },
    });
    expect(meRes.ok()).toBeTruthy();
    const me = await meRes.json();
    expect(me.email).toBe(email);
  });

  test("duplicate registration returns a conflict error", async ({ request }) => {
    const res = await request.post(`${apiUrl}/auth/register`, {
      data: { email: env.userEmail(), password: "Str0ng!Passw0rd" },
    });
    expect([400, 409, 422]).toContain(res.status());
  });

  test("login with wrong password is rejected with 401", async ({ request }) => {
    const res = await request.post(`${apiUrl}/auth/login`, {
      form: { username: env.userEmail(), password: "definitely-wrong" },
    });
    expect(res.status()).toBe(401);
  });

  test("login with unknown account is rejected with 401", async ({ request }, testInfo) => {
    const res = await request.post(`${apiUrl}/auth/login`, {
      form: { username: `unknown-${runId(testInfo.workerIndex)}@example.com`, password: "whatever123!" },
    });
    expect(res.status()).toBe(401);
  });

  test("token refresh returns a new access token", async ({ request }) => {
    const loginRes = await request.post(`${apiUrl}/auth/login`, {
      form: { username: env.userEmail(), password: env.userPassword() },
    });
    const { refresh_token } = await loginRes.json();

    const refreshRes = await request.post(`${apiUrl}/auth/refresh`, {
      data: { refresh_token },
    });
    expect(refreshRes.ok()).toBeTruthy();
    const refreshed = await refreshRes.json();
    expect(refreshed.access_token).toBeTruthy();
  });

  test("malformed JSON body is rejected with a client error, not a 5xx", async ({ request }) => {
    const res = await request.post(`${apiUrl}/auth/register`, {
      headers: { "Content-Type": "application/json" },
      data: "{not valid json",
    });
    expect(res.status()).toBeGreaterThanOrEqual(400);
    expect(res.status()).toBeLessThan(500);
  });

  test("unsupported media type on login form endpoint is rejected cleanly", async ({ request }) => {
    const res = await request.post(`${apiUrl}/auth/login`, {
      headers: { "Content-Type": "application/json" },
      data: { username: env.userEmail(), password: env.userPassword() },
    });
    // OAuth2PasswordRequestForm expects form-encoded data, not JSON.
    expect(res.status()).toBeGreaterThanOrEqual(400);
    expect(res.status()).toBeLessThan(500);
  });
});
