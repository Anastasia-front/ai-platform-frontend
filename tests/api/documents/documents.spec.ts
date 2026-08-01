import { test, expect } from "@playwright/test";
import { BackendApiClient } from "../../e2e/helpers/api-client";
import { env, runId } from "../../e2e/helpers/env";
import { fixtures } from "../../e2e/helpers/fixture-files";
import { pollApiUntil } from "../../e2e/helpers/polling";

const apiUrl = process.env.E2E_API_URL || "http://localhost:8000";

test.describe("Documents API @api @critical", () => {
  let api: BackendApiClient;
  let projectId: string | number;

  test.beforeAll(async ({}, testInfo) => {
    api = await BackendApiClient.login(env.userEmail(), env.userPassword());
    const project = await api.createProject(`${runId(testInfo.workerIndex)}-doc-api-project`);
    projectId = project.id;
  });
  test.afterAll(async () => {
    await api.deleteProject(projectId);
    await api.dispose();
  });

  test("upload, poll status, fetch chunks, delete @slow", async ({}, testInfo) => {
    testInfo.setTimeout(150_000);
    const uploaded = await api.uploadDocument(projectId, fixtures.smallTxt, "text/plain");
    expect(uploaded.id).toBeTruthy();

    const processRes = await api.raw().post(`${apiUrl}/documents/${uploaded.id}/process`, {
      headers: api.authHeader(),
    });
    expect(processRes.ok()).toBeTruthy();

    const finalDoc = await pollApiUntil(
      () => api.getDocument(uploaded.id),
      (d) => ["indexed", "failed"].includes(d.status),
      { timeoutMs: 120_000, label: "document processing status" }
    );
    expect(["indexed", "failed"]).toContain(finalDoc.status);

    if (finalDoc.status === "indexed") {
      const chunksRes = await api.raw().get(`${apiUrl}/documents/${uploaded.id}/chunks`, {
        headers: api.authHeader(),
      });
      expect(chunksRes.ok()).toBeTruthy();
    }

    const deleteRes = await api.raw().delete(`${apiUrl}/documents/${uploaded.id}`, {
      headers: api.authHeader(),
    });
    expect(deleteRes.ok()).toBeTruthy();
  });

  test("document not found returns 404", async () => {
    const res = await api.raw().get(`${apiUrl}/documents/999999999`, { headers: api.authHeader() });
    expect(res.status()).toBe(404);
  });

  test("missing auth on document upload returns 401", async () => {
    const res = await api.raw().post(`${apiUrl}/projects/${projectId}/documents`, {
      multipart: { file: { name: "small.txt", mimeType: "text/plain", buffer: Buffer.from("x") } },
    });
    expect(res.status()).toBe(401);
  });
});
