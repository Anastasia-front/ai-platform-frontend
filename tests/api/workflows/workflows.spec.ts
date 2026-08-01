import { test, expect } from "@playwright/test";
import { BackendApiClient } from "../../e2e/helpers/api-client";
import { env, runId } from "../../e2e/helpers/env";
import { pollApiUntil } from "../../e2e/helpers/polling";

const apiUrl = process.env.E2E_API_URL || "http://localhost:8000";

test.describe("Workflows API @api @critical", () => {
  let api: BackendApiClient;
  let projectId: string | number;

  test.beforeAll(async ({}, testInfo) => {
    api = await BackendApiClient.login(env.userEmail(), env.userPassword());
    const project = await api.createProject(`${runId(testInfo.workerIndex)}-workflow-api-project`);
    projectId = project.id;
  });
  test.afterAll(async () => {
    await api.deleteProject(projectId);
    await api.dispose();
  });

  test("create workflow, add step, run, poll to terminal status @slow", async ({}, testInfo) => {
    testInfo.setTimeout(210_000);
    const workflow = await api.createWorkflow(projectId, `${runId(testInfo.workerIndex)}-workflow`);
    expect(workflow.id).toBeTruthy();

    const stepRes = await api.raw().post(`${apiUrl}/workflows/${workflow.id}/steps`, {
      headers: api.authHeader(),
      data: { step_order: 1, name: "step-1", prompt_template: "Echo: {input}" },
    });
    expect(stepRes.ok()).toBeTruthy();

    const run = await api.runWorkflow(workflow.id);
    expect(run.id).toBeTruthy();
    expect(["pending", "running"]).toContain(run.status);

    const finalRun = await pollApiUntil(
      () => api.getRun(run.id),
      (r) => ["completed", "failed", "canceled", "paused"].includes(r.status),
      { timeoutMs: 180_000, label: "workflow run status" }
    );
    expect(["completed", "failed", "canceled", "paused"]).toContain(finalRun.status);
  });

  test("invalid workflow step configuration is rejected", async ({}, testInfo) => {
    const workflow = await api.createWorkflow(projectId, `${runId(testInfo.workerIndex)}-invalid-step-workflow`);
    const res = await api.raw().post(`${apiUrl}/workflows/${workflow.id}/steps`, {
      headers: api.authHeader(),
      data: { step_order: 1 }, // missing required name/prompt_template
    });
    expect(res.status()).toBe(422);
  });

  test("cancel, retry, resume endpoints respond with a sensible status", async ({}, testInfo) => {
    const workflow = await api.createWorkflow(projectId, `${runId(testInfo.workerIndex)}-crr-workflow`);
    await api.raw().post(`${apiUrl}/workflows/${workflow.id}/steps`, {
      headers: api.authHeader(),
      data: { step_order: 1, name: "step-1", prompt_template: "Echo: {input}" },
    });
    const run = await api.runWorkflow(workflow.id);

    const cancelRes = await api.raw().post(`${apiUrl}/runs/${run.id}/cancel`, { headers: api.authHeader() });
    expect([200, 202, 409]).toContain(cancelRes.status());

    const retryRes = await api.raw().post(`${apiUrl}/runs/${run.id}/retry`, { headers: api.authHeader() });
    expect([200, 202, 400, 409]).toContain(retryRes.status());

    const resumeRes = await api.raw().post(`${apiUrl}/runs/${run.id}/resume`, { headers: api.authHeader() });
    expect([200, 202, 400, 409]).toContain(resumeRes.status());
  });

  test("workflow not found returns 404", async () => {
    const res = await api.raw().get(`${apiUrl}/workflows/999999999`, { headers: api.authHeader() });
    expect(res.status()).toBe(404);
  });
});
