import { test, expect } from "@playwright/test";
import { BackendApiClient } from "../../e2e/helpers/api-client";
import { env, runId } from "../../e2e/helpers/env";

const apiUrl = process.env.E2E_API_URL || "http://localhost:8000";

test.describe("Projects API @api @critical", () => {
  let api: BackendApiClient;

  test.beforeAll(async () => {
    api = await BackendApiClient.login(env.userEmail(), env.userPassword());
  });
  test.afterAll(async () => {
    await api.dispose();
  });

  test("full CRUD lifecycle", async ({}, testInfo) => {
    const name = `${runId(testInfo.workerIndex)}-project`;
    const created = await api.createProject(name);
    expect(created.id).toBeTruthy();
    expect(created.name).toBe(name);

    const getRes = await api.raw().get(`${apiUrl}/projects/${created.id}`, { headers: api.authHeader() });
    expect(getRes.ok()).toBeTruthy();

    const patchRes = await api.raw().patch(`${apiUrl}/projects/${created.id}`, {
      headers: api.authHeader(),
      data: { name: `${name}-updated` },
    });
    expect(patchRes.ok()).toBeTruthy();
    expect((await patchRes.json()).name).toBe(`${name}-updated`);

    const listRes = await api.raw().get(`${apiUrl}/projects/`, { headers: api.authHeader() });
    expect(listRes.ok()).toBeTruthy();
    const list = await listRes.json();
    expect(Array.isArray(list) || Array.isArray(list.items)).toBeTruthy();

    await api.deleteProject(created.id);
    const getAfterDelete = await api.raw().get(`${apiUrl}/projects/${created.id}`, {
      headers: api.authHeader(),
    });
    expect([403, 404]).toContain(getAfterDelete.status());
  });

  test("empty name is currently accepted at the API layer (validation is frontend-only)", async ({}, testInfo) => {
    // app/schemas/project.py::ProjectCreate.name has no min_length — the
    // backend does not reject "" today; only the Django form does
    // ("Project name is required."). This documents current behavior
    // rather than asserting a stricter contract the API doesn't enforce.
    // See TEST_PLAN.md "Known gaps" for the recommendation to add
    // server-side validation.
    const res = await api.raw().post(`${apiUrl}/projects/`, {
      headers: api.authHeader(),
      data: { name: "" },
    });
    expect(res.status()).toBe(201);
    const created = await res.json();
    await api.deleteProject(created.id);
  });

  test("not-found project returns 404", async () => {
    const res = await api.raw().get(`${apiUrl}/projects/999999999`, { headers: api.authHeader() });
    expect(res.status()).toBe(404);
  });

  test("missing auth on project list returns 401", async () => {
    const res = await api.raw().get(`${apiUrl}/projects/`);
    expect(res.status()).toBe(401);
  });
});
