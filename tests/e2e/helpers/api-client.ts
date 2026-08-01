import { APIRequestContext, request as pwRequest } from "@playwright/test";
import { env } from "./env";

/**
 * Direct client for the FastAPI backend, used for test-data setup/cleanup
 * so E2E tests don't depend on the UI to create their own fixtures.
 */
export class BackendApiClient {
  private constructor(
    private readonly ctx: APIRequestContext,
    private accessToken: string
  ) {}

  static async login(email: string, password: string): Promise<BackendApiClient> {
    const ctx = await pwRequest.newContext({ baseURL: env.apiUrl() });
    const res = await ctx.post("/auth/login", {
      form: { username: email, password },
    });
    if (!res.ok()) {
      throw new Error(
        `Backend login failed for ${email}: ${res.status()} ${await res.text()}`
      );
    }
    const body = await res.json();
    return new BackendApiClient(ctx, body.access_token);
  }

  private authHeaders() {
    return { Authorization: `Bearer ${this.accessToken}` };
  }

  async createProject(name: string) {
    const res = await this.ctx.post("/projects/", {
      headers: this.authHeaders(),
      data: { name },
    });
    if (!res.ok()) throw new Error(`createProject failed: ${res.status()} ${await res.text()}`);
    return res.json();
  }

  async deleteProject(projectId: string | number) {
    await this.ctx.delete(`/projects/${projectId}`, { headers: this.authHeaders() });
  }

  async createChat(projectId: string | number, title?: string) {
    const res = await this.ctx.post(`/projects/${projectId}/chats`, {
      headers: this.authHeaders(),
      data: title ? { title } : {},
    });
    if (!res.ok()) throw new Error(`createChat failed: ${res.status()} ${await res.text()}`);
    return res.json();
  }

  async uploadDocument(projectId: string | number, filePath: string, mimeType: string) {
    const fs = await import("fs");
    const path = await import("path");
    const res = await this.ctx.post(`/projects/${projectId}/documents`, {
      headers: this.authHeaders(),
      multipart: {
        file: {
          name: path.basename(filePath),
          mimeType,
          buffer: fs.readFileSync(filePath),
        },
      },
    });
    if (!res.ok()) throw new Error(`uploadDocument failed: ${res.status()} ${await res.text()}`);
    return res.json();
  }

  async getDocument(documentId: string | number) {
    const res = await this.ctx.get(`/documents/${documentId}`, { headers: this.authHeaders() });
    if (!res.ok()) throw new Error(`getDocument failed: ${res.status()} ${await res.text()}`);
    return res.json();
  }

  async createWorkflow(projectId: string | number, name: string) {
    const res = await this.ctx.post(`/projects/${projectId}/workflows`, {
      headers: this.authHeaders(),
      data: { name },
    });
    if (!res.ok()) throw new Error(`createWorkflow failed: ${res.status()} ${await res.text()}`);
    return res.json();
  }

  async runWorkflow(workflowId: string | number, input = "Playwright E2E test input") {
    // WorkflowRunRequest requires a non-empty `input` string (see backend
    // app/schemas/workflow_run.py) — omitting it 422s with "Field required".
    const res = await this.ctx.post(`/workflows/${workflowId}/run`, {
      headers: this.authHeaders(),
      data: { input },
    });
    if (!res.ok()) throw new Error(`runWorkflow failed: ${res.status()} ${await res.text()}`);
    return res.json();
  }

  async getRun(runId: string | number) {
    const res = await this.ctx.get(`/runs/${runId}`, { headers: this.authHeaders() });
    if (!res.ok()) throw new Error(`getRun failed: ${res.status()} ${await res.text()}`);
    return res.json();
  }

  async me() {
    const res = await this.ctx.get("/auth/me", { headers: this.authHeaders() });
    if (!res.ok()) throw new Error(`me failed: ${res.status()} ${await res.text()}`);
    return res.json();
  }

  raw(): APIRequestContext {
    return this.ctx;
  }

  authHeader(): Record<string, string> {
    return this.authHeaders();
  }

  async dispose() {
    await this.ctx.dispose();
  }
}
