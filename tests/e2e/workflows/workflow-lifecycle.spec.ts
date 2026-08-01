import { expect, test } from "../fixtures/base";
import { waitForStatusText } from "../helpers/polling";
import { uniqueName } from "../helpers/test-data";

/**
 * Step names render inside the `<summary>` of the collapsed-by-default
 * `<details class="workflow-description-dropdown">` panel. Every form
 * submit on this page (Add Step, page reload) redirects back to a fresh,
 * collapsed render — the step text exists in the DOM but stays hidden
 * until the panel is reopened.
 *
 * Set `.open` directly via JS rather than clicking the `<summary>`: this
 * panel nests further `<details class="workflow-step-accordion">` per step,
 * and WebKit's hit-testing for nested details/summary intercepts clicks on
 * the parent element, making a real click unreliable there. Setting the
 * property is what a click does under the hood anyway.
 */
async function openWorkflowDetails(page: import("@playwright/test").Page) {
  await page.locator(".workflow-description-dropdown").evaluate((el) => {
    (el as HTMLDetailsElement).open = true;
  });
}

test.describe("Workflow create, configure and run @critical", () => {
  test("create a workflow, add a step, save and reload persists it @smoke", async ({
    page,
    primaryApi,
  }, testInfo) => {
    const project = await primaryApi.createProject(
      uniqueName("workflow-project", testInfo.workerIndex),
    );
    const workflowName = uniqueName("workflow", testInfo.workerIndex);
    const projectSlug = String(project.name)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-");

    await page.goto(`/workflows/?project=${projectSlug}`);
    await page.getByPlaceholder("Workflow name").fill(workflowName);
    await page.getByRole("button", { name: "Create Workflow" }).click();

    await expect(
      page.getByRole("heading", { name: workflowName }),
    ).toBeVisible();

    await page.getByPlaceholder("Validate order").fill("Summarize input");
    await page
      .getByPlaceholder(/use \{input\}/i)
      .fill("Summarize the following: {input}");
    await page.getByRole("button", { name: "Add Step" }).click();

    await openWorkflowDetails(page);
    // exact:true matters here — the "depends on" field's own hint text
    // dynamically lists existing step names as an example (e.g. "...e.g.
    // 132: Summarize input"), which would also substring-match otherwise.
    await expect(page.getByText("Summarize input", { exact: true })).toBeVisible();

    await page.reload();
    await openWorkflowDetails(page);
    await expect(page.getByText("Summarize input", { exact: true })).toBeVisible();

    await primaryApi.deleteProject(project.id);
  });

  test("invalid workflow configuration (empty name) is rejected client-side", async ({
    page,
    primaryApi,
  }, testInfo) => {
    // The "Create Workflow" form only renders once a project is selected
    // via ?project=<slug> (see dashboard/templates/dashboard/utility/workflows.html
    // — form is gated on `workflow_project`), so a project must exist first.
    const project = await primaryApi.createProject(
      uniqueName("workflow-invalid-project", testInfo.workerIndex),
    );
    const projectSlug = String(project.name).toLowerCase().replace(/[^a-z0-9]+/g, "-");

    await page.goto(`/workflows/?project=${projectSlug}`);
    const nameInput = page.getByPlaceholder("Workflow name");
    await page.getByRole("button", { name: "Create Workflow" }).click();
    // The `name` input is HTML5 `required` — an empty submit is blocked
    // client-side rather than producing a server-rendered flash message.
    const isValid = await nameInput.evaluate((el: HTMLInputElement) => el.checkValidity());
    expect(isValid).toBe(false);

    await primaryApi.deleteProject(project.id);
  });

  test("run workflow via test input reaches a terminal status @slow", async ({
    page,
    primaryApi,
  }, testInfo) => {
    const project = await primaryApi.createProject(
      uniqueName("workflow-run-project", testInfo.workerIndex),
    );
    const workflowName = uniqueName("workflow-run", testInfo.workerIndex);
    const projectSlug = String(project.name)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-");

    await page.goto(`/workflows/?project=${projectSlug}`);
    await page.getByPlaceholder("Workflow name").fill(workflowName);
    await page.getByRole("button", { name: "Create Workflow" }).click();

    await page.getByPlaceholder("Validate order").fill("Echo input");
    await page.getByPlaceholder(/use \{input\}/i).fill("Echo: {input}");
    await page.getByRole("button", { name: "Add Step" }).click();

    await page
      .getByPlaceholder(/paste a test input/i)
      .fill("Playwright E2E test input");
    await page.getByRole("button", { name: "Run Workflow" }).click();

    await page.waitForURL(/\/executions\/\d+\//);
    const status = page
      .locator("[data-execution-status], .status-badge")
      .first();
    await waitForStatusText(status, /completed|failed/, {
      timeoutMs: 180_000,
      label: "workflow run status",
    });

    await primaryApi.deleteProject(project.id);
  });

  test("step dependency and condition metadata render (DAG branching) @regression", async ({
    page,
    primaryApi,
  }, testInfo) => {
    const project = await primaryApi.createProject(
      uniqueName("workflow-dag-project", testInfo.workerIndex),
    );
    const workflowName = uniqueName("workflow-dag", testInfo.workerIndex);
    const projectSlug = String(project.name).toLowerCase().replace(/[^a-z0-9]+/g, "-");

    await page.goto(`/workflows/?project=${projectSlug}`);
    await page.getByPlaceholder("Workflow name").fill(workflowName);
    await page.getByRole("button", { name: "Create Workflow" }).click();

    // Step 1: no dependencies.
    await page.getByPlaceholder("Validate order").fill("Gather input");
    await page.getByPlaceholder(/use \{input\}/i).fill("Restate: {input}");
    await page.getByRole("button", { name: "Add Step" }).click();

    // Step 2: depends on step 1 and only runs under a condition — this is
    // the DAG branching data model (see app/schemas/workflow_step.py's
    // `depends_on`/`condition` fields on the backend).
    await page.getByPlaceholder("Validate order").fill("Conditional summary");
    await page.getByPlaceholder(/use \{input\}/i).fill("Summarize: {input}");
    await page.getByPlaceholder("1, 2").fill("1");
    await page.getByPlaceholder("Optional condition").fill("previous.length > 0");
    await page.getByRole("button", { name: "Add Step" }).click();

    await openWorkflowDetails(page);
    const stepTwo = page.locator(".workflow-step-accordion", {
      hasText: "Conditional summary",
    });
    await stepTwo.evaluate((el) => {
      (el as HTMLDetailsElement).open = true;
    });

    await expect(stepTwo.getByText("Depends on: 1")).toBeVisible();
    await expect(stepTwo.getByText("Condition: previous.length > 0")).toBeVisible();

    await primaryApi.deleteProject(project.id);
  });

  test("delete a workflow removes it from the list @regression", async ({
    page,
    primaryApi,
  }, testInfo) => {
    const project = await primaryApi.createProject(
      uniqueName("workflow-delete-project", testInfo.workerIndex),
    );
    const workflowName = uniqueName("workflow-delete", testInfo.workerIndex);
    const projectSlug = String(project.name)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-");

    await page.goto(`/workflows/?project=${projectSlug}`);
    await page.getByPlaceholder("Workflow name").fill(workflowName);
    await page.getByRole("button", { name: "Create Workflow" }).click();
    await expect(
      page.getByRole("heading", { name: workflowName }),
    ).toBeVisible();

    await page.getByRole("button", { name: "Delete Workflow" }).click();
    await expect(page.getByText(workflowName)).toHaveCount(0);

    await primaryApi.deleteProject(project.id);
  });
});

test.describe("Workflow ownership @critical", () => {
  test("user cannot access another user's workflow", async ({
    primaryApi,
    secondaryApi,
  }, testInfo) => {
    const project = await secondaryApi.createProject(
      uniqueName("secondary-workflow-project", testInfo.workerIndex),
    );
    const workflow = await secondaryApi.createWorkflow(
      project.id,
      uniqueName("secondary-workflow", testInfo.workerIndex),
    );

    const res = await primaryApi
      .raw()
      .get(
        `${process.env.E2E_API_URL || "http://localhost:8000"}/workflows/${workflow.id}`,
        {
          headers: primaryApi.authHeader(),
        },
      );
    expect([403, 404]).toContain(res.status());

    await secondaryApi.deleteProject(project.id);
  });
});
