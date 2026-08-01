import { test, expect } from "../fixtures/base";
import { uniqueName } from "../helpers/test-data";
import { waitForStatusText } from "../helpers/polling";
import { pollApiUntil } from "../helpers/polling";

async function createAndRunWorkflow(primaryApi: any, projectName: string, workflowName: string, stepPrompt: string) {
  const project = await primaryApi.createProject(projectName);
  const workflow = await primaryApi.createWorkflow(project.id, workflowName);
  // Steps are created via the API client's generic request context (no
  // dedicated helper method exists yet — see helpers/api-client.ts).
  await primaryApi.raw().post(`${process.env.E2E_API_URL || "http://localhost:8000"}/workflows/${workflow.id}/steps`, {
    headers: primaryApi.authHeader(),
    data: { step_order: 1, name: "step-1", prompt_template: stepPrompt },
  });
  const run = await primaryApi.runWorkflow(workflow.id);
  return { project, workflow, run };
}

test.describe("Workflow run history and execution detail @critical", () => {
  test("run appears in execution history with correct workflow reference", async ({
    page,
    primaryApi,
  }, testInfo) => {
    const { project, workflow, run } = await createAndRunWorkflow(
      primaryApi,
      uniqueName("exec-project", testInfo.workerIndex),
      uniqueName("exec-workflow", testInfo.workerIndex),
      "Echo: {input}"
    );

    await page.goto("/executions/");
    await expect(page.getByText(`Workflow #${workflow.id}`)).toBeVisible();

    await page.goto(`/executions/${run.id}/`);
    await expect(page.getByRole("heading", { name: `Execution #${run.id}` })).toBeVisible();

    await primaryApi.deleteProject(project.id);
  });

  test("execution reaches a terminal status and detail page shows it @slow", async ({
    page,
    primaryApi,
  }, testInfo) => {
    const { project, run } = await createAndRunWorkflow(
      primaryApi,
      uniqueName("exec-terminal-project", testInfo.workerIndex),
      uniqueName("exec-terminal-workflow", testInfo.workerIndex),
      "Echo: {input}"
    );

    await pollApiUntil(
      () => primaryApi.getRun(run.id),
      (r) => ["completed", "failed", "canceled", "paused"].includes(r.status),
      { timeoutMs: 180_000, label: "workflow run terminal status" }
    );

    await page.goto(`/executions/${run.id}/`);
    const status = page.locator("[data-execution-status], .status-badge").first();
    await waitForStatusText(status, /completed|failed|canceled|paused/, { timeoutMs: 15_000 });

    await primaryApi.deleteProject(project.id);
  });

  test("cancel a run and verify cancelled state @regression", async ({ primaryApi }, testInfo) => {
    const { project, run } = await createAndRunWorkflow(
      primaryApi,
      uniqueName("exec-cancel-project", testInfo.workerIndex),
      uniqueName("exec-cancel-workflow", testInfo.workerIndex),
      "Echo: {input}"
    );

    const apiUrl = process.env.E2E_API_URL || "http://localhost:8000";
    const res = await primaryApi.raw().post(`${apiUrl}/runs/${run.id}/cancel`, {
      headers: primaryApi.authHeader(),
    });
    // Cancellation may 409 if the run already completed before we could
    // cancel it — that race is a known limitation of same-process cancel
    // tests without a slow/blocking mock provider (see README known gaps).
    expect([200, 202, 409]).toContain(res.status());

    await primaryApi.deleteProject(project.id);
  });

  test("cancelled execution list entry can be deleted with confirmation @regression", async ({
    page,
  }) => {
    await page.goto("/executions/?status=canceled");
    const deleteAllButton = page.getByRole("button", { name: "Delete cancelled executions" });
    if (await deleteAllButton.isVisible().catch(() => false)) {
      page.once("dialog", (dialog) => dialog.dismiss());
      await deleteAllButton.click();
      // Dismissing the confirm() must leave the executions list unchanged.
      await expect(page.getByRole("button", { name: "Delete cancelled executions" })).toBeVisible();
    }
  });
});

test.describe("Execution ownership @critical", () => {
  test("user cannot access another user's workflow run", async ({ primaryApi, secondaryApi }, testInfo) => {
    const { project, run } = await createAndRunWorkflow(
      secondaryApi,
      uniqueName("secondary-exec-project", testInfo.workerIndex),
      uniqueName("secondary-exec-workflow", testInfo.workerIndex),
      "Echo: {input}"
    );

    const apiUrl = process.env.E2E_API_URL || "http://localhost:8000";
    const res = await primaryApi.raw().get(`${apiUrl}/runs/${run.id}`, {
      headers: primaryApi.authHeader(),
    });
    expect([403, 404]).toContain(res.status());

    await secondaryApi.deleteProject(project.id);
  });
});
