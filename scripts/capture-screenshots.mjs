#!/usr/bin/env node
/**
 * One-off script (not part of the E2E test suite) to generate clean,
 * presentation-ready screenshots for the README -- populated with nice-
 * looking demo data instead of the e2e-* fixture names the test suite
 * uses, and without the mask boxes visual-regression screenshots have.
 *
 * Run against a local stack (see scripts/test-e2e.sh up):
 *   node scripts/capture-screenshots.mjs
 *
 * Env overrides: BASE_URL (default http://localhost:8001),
 * API_URL (default http://localhost:8000), OUT_DIR (default docs/screenshots),
 * POSTGRES_CONTAINER (default ai-platform-postgres).
 */
import { chromium } from "@playwright/test";
import { execFileSync } from "child_process";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const BASE_URL = process.env.BASE_URL || "http://localhost:8001";
const API_URL = process.env.API_URL || "http://localhost:8000";
const OUT_DIR =
  process.env.OUT_DIR || path.join(__dirname, "..", "docs", "screenshots");
const POSTGRES_CONTAINER =
  process.env.POSTGRES_CONTAINER || "ai-platform-postgres";
const FIXTURES_DIR = path.join(__dirname, "..", "tests", "e2e", "test-data");

const DEMO_EMAIL = "presentation@demo.com";
const DEMO_PASSWORD = "DemoPresentation123!";

fs.mkdirSync(OUT_DIR, { recursive: true });

async function apiFetch(pathname, options = {}) {
  const res = await fetch(`${API_URL}${pathname}`, options);
  return res;
}

async function ensureDemoUserAndToken() {
  // Idempotent: ignore "already exists" on repeat runs.
  await apiFetch("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: DEMO_EMAIL, password: DEMO_PASSWORD }),
  });

  const loginRes = await apiFetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      username: DEMO_EMAIL,
      password: DEMO_PASSWORD,
    }),
  });
  if (!loginRes.ok) {
    throw new Error(
      `Demo user login failed: ${loginRes.status} ${await loginRes.text()}`,
    );
  }
  const { access_token } = await loginRes.json();
  return access_token;
}

async function seedDemoData(token) {
  const authHeaders = {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };

  // Project/chat/workflow names aren't unique server-side, so re-running
  // this script would otherwise pile up duplicates in the sidebar --
  // check what already exists first and reuse it.
  async function listProjects() {
    const res = await apiFetch("/projects/", { headers: authHeaders });
    if (!res.ok)
      throw new Error(`listProjects failed: ${res.status} ${await res.text()}`);
    return res.json();
  }

  async function createProject(name) {
    const res = await apiFetch("/projects/", {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({ name }),
    });
    if (!res.ok)
      throw new Error(
        `createProject(${name}) failed: ${res.status} ${await res.text()}`,
      );
    return res.json();
  }

  async function getOrCreateProject(name, existing) {
    const found = existing.find((p) => p.name === name);
    if (found) return found;
    return createProject(name);
  }

  async function listChats(projectId) {
    const res = await apiFetch(`/projects/${projectId}/chats`, {
      headers: authHeaders,
    });
    if (!res.ok)
      throw new Error(`listChats failed: ${res.status} ${await res.text()}`);
    return res.json();
  }

  async function createChat(projectId, title) {
    const res = await apiFetch(`/projects/${projectId}/chats`, {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({ title }),
    });
    if (!res.ok)
      throw new Error(
        `createChat(${title}) failed: ${res.status} ${await res.text()}`,
      );
    return res.json();
  }

  async function getOrCreateChat(projectId, title) {
    const existing = await listChats(projectId);
    const found = existing.find((c) => c.title === title);
    if (found) return found;
    return createChat(projectId, title);
  }

  async function listWorkflows(projectId) {
    const res = await apiFetch(`/projects/${projectId}/workflows`, {
      headers: authHeaders,
    });
    if (!res.ok)
      throw new Error(
        `listWorkflows failed: ${res.status} ${await res.text()}`,
      );
    return res.json();
  }

  async function createWorkflow(projectId, name) {
    const res = await apiFetch(`/projects/${projectId}/workflows`, {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({ name }),
    });
    if (!res.ok)
      throw new Error(
        `createWorkflow(${name}) failed: ${res.status} ${await res.text()}`,
      );
    return res.json();
  }

  async function getOrCreateWorkflow(projectId, name) {
    const existing = await listWorkflows(projectId);
    const found = existing.find((w) => w.name === name);
    if (found) return found;
    return createWorkflow(projectId, name);
  }

  async function listDocuments(projectId) {
    const res = await apiFetch(`/projects/${projectId}/documents`, {
      headers: authHeaders,
    });
    if (!res.ok)
      throw new Error(
        `listDocuments failed: ${res.status} ${await res.text()}`,
      );
    return res.json();
  }

  async function uploadDocument(projectId, fixtureFile, displayName, mimeType) {
    const buffer = fs.readFileSync(path.join(FIXTURES_DIR, fixtureFile));
    const form = new FormData();
    form.append("file", new Blob([buffer], { type: mimeType }), displayName);
    const res = await apiFetch(`/projects/${projectId}/documents`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    });
    if (!res.ok)
      throw new Error(
        `uploadDocument(${displayName}) failed: ${res.status} ${await res.text()}`,
      );
    return res.json();
  }

  async function getOrUploadDocument(
    projectId,
    fixtureFile,
    displayName,
    mimeType,
    existing,
  ) {
    const found = existing.find((d) => d.filename === displayName);
    if (found) return found;
    return uploadDocument(projectId, fixtureFile, displayName, mimeType);
  }

  // Presentation-friendly names -- deliberately not "e2e-*" like the test suite uses.
  const existingProjects = await listProjects();
  const support = await getOrCreateProject(
    "Customer Support Assistant",
    existingProjects,
  );
  const content = await getOrCreateProject(
    "Content Generation Pipeline",
    existingProjects,
  );
  const knowledgeBase = await getOrCreateProject(
    "Internal Knowledge Base",
    existingProjects,
  );

  const chat = await getOrCreateChat(support.id, "Refund policy question");
  const workflow = await getOrCreateWorkflow(content.id, "Blog post pipeline");

  console.log("Uploading demo documents...");
  const supportDocs = await listDocuments(support.id);
  await getOrUploadDocument(
    support.id,
    "small.pdf",
    "refund-policy-faq.pdf",
    "application/pdf",
    supportDocs,
  );

  const kbDocs = await listDocuments(knowledgeBase.id);
  await getOrUploadDocument(
    knowledgeBase.id,
    "small.pdf",
    "product-overview.pdf",
    "application/pdf",
    kbDocs,
  );
  await getOrUploadDocument(
    knowledgeBase.id,
    "small.md",
    "onboarding-guide.md",
    "text/markdown",
    kbDocs,
  );
  await getOrUploadDocument(
    knowledgeBase.id,
    "small.txt",
    "support-escalation-process.txt",
    "text/plain",
    kbDocs,
  );

  return { support, content, knowledgeBase, chat, workflow };
}

// Real runs need a working AI provider chain, which a local dev machine
// usually doesn't have wired up end-to-end -- insert workflow_run rows
// directly via psql in the Postgres container instead, so the executions
// screenshot can show a realistic mix of terminal statuses on demand.
function seedExecutionHistory(workflowId) {
  console.log("Seeding demo execution history (completed/failed/canceled)...");
  const runs = [
    {
      status: "completed",
      input: "Write a 500-word blog post announcing our new pricing tiers.",
      output:
        'Draft generated: "Simpler Pricing, Bigger Value" -- 512 words, 3 sections, CTA included.',
      error: null,
      minutesAgo: 45,
    },
    {
      status: "failed",
      input: "Summarize competitor pricing pages into a comparison table.",
      output: null,
      error:
        "Provider request timed out after 60s (openrouter -> ollama fallback exhausted).",
      minutesAgo: 20,
    },
    {
      status: "canceled",
      input: "Generate 10 social captions for the Q3 product launch.",
      output: null,
      error: null,
      minutesAgo: 5,
    },
  ];

  for (const run of runs) {
    const sql = `
      INSERT INTO workflow_runs (workflow_id, input, output, status, error, created_at, updated_at)
      SELECT ${workflowId}, $$${run.input}$$, ${run.output ? `$$${run.output}$$` : "NULL"},
             '${run.status}', ${run.error ? `$$${run.error}$$` : "NULL"},
             NOW() - INTERVAL '${run.minutesAgo} minutes', NOW() - INTERVAL '${run.minutesAgo - 2} minutes'
      WHERE NOT EXISTS (
        SELECT 1 FROM workflow_runs WHERE workflow_id = ${workflowId} AND status = '${run.status}'
      );
    `;
    execFileSync(
      "docker",
      [
        "exec",
        "-i",
        POSTGRES_CONTAINER,
        "psql",
        "-U",
        "postgres",
        "-d",
        "ai_platform",
        "-v",
        "ON_ERROR_STOP=1",
      ],
      { input: sql, stdio: ["pipe", "inherit", "inherit"] },
    );
  }
}

// provider_configs is seeded once from env at first backend startup, so
// editing CHAT_BASE_URL/EMBEDDING_BASE_URL in .env after that point doesn't
// retroactively update the Ollama row the providers page reads from --
// update it directly so the screenshot shows a presentable internal
// hostname instead of localhost.
function fixOllamaProviderUrl() {
  const sql = `UPDATE provider_configs SET base_url = 'http://ollama.ai-platform.internal:11434' WHERE provider = 'ollama';`;
  execFileSync(
    "docker",
    [
      "exec",
      "-i",
      POSTGRES_CONTAINER,
      "psql",
      "-U",
      "postgres",
      "-d",
      "ai_platform",
      "-v",
      "ON_ERROR_STOP=1",
    ],
    { input: sql, stdio: ["pipe", "inherit", "inherit"] },
  );
}

async function loginViaUi(page) {
  await page.goto(`${BASE_URL}/login/`);
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password", { exact: true }).fill(DEMO_PASSWORD);
  await page.getByRole("button", { name: "Log in" }).click();
  await page.waitForURL(/\/projects\//);
}

function sseFrame(event, data) {
  return `event: ${event}\ndata: ${JSON.stringify({ event, ...data })}\n\n`;
}

async function mockChatReply(page, text) {
  await page.route("**/messages/stream/", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: sseFrame("completed", { content: text }),
    });
  });
}

async function shot(page, name) {
  await page.screenshot({
    path: path.join(OUT_DIR, `${name}.png`),
    fullPage: true,
  });
  console.log(`  saved ${name}.png`);
}

async function main() {
  console.log(`Seeding demo data via ${API_URL} ...`);
  const token = await ensureDemoUserAndToken();
  const demo = await seedDemoData(token);
  seedExecutionHistory(demo.workflow.id);
  fixOllamaProviderUrl();

  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();

  console.log("Capturing logged-out pages...");
  await page.goto(`${BASE_URL}/login/`);
  await shot(page, "login");

  await page.goto(`${BASE_URL}/register/`);
  await page.getByLabel("Email").fill("new.hire@ai-automation-platform.com");
  await page.getByLabel("Password", { exact: true }).fill("StrongPassword123!");
  await shot(page, "register");

  console.log("Logging in as demo user...");
  await loginViaUi(page);
  await shot(page, "projects");

  const supportSlug = String(demo.support.name)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-");
  await page.goto(`${BASE_URL}/projects/${supportSlug}/`);

  console.log("Simulating a chat conversation...");
  await mockChatReply(
    page,
    "You can request a refund within 30 days of purchase. I've opened a ticket on your behalf -- reference #SR-4821.",
  );
  // The composer only renders once a chat is selected -- click it open
  // from the sidebar rather than assuming the project root shows it.
  await page.getByText(demo.chat.title || "Refund policy question").click();
  await page.waitForURL(/\/chats\//);
  const composer = page.getByPlaceholder("Message the assistant...");
  await composer.fill(
    "A customer is asking about our refund policy for a purchase made 3 weeks ago.",
  );
  await page.getByRole("button", { name: "Send" }).click();
  await page.waitForTimeout(500);
  // Documents accordion is on the same project workspace page as chat --
  // force it open so the uploaded refund-policy-faq.pdf is visible too.
  const chatDocsAccordion = page.locator(".documents-accordion");
  if (await chatDocsAccordion.count()) {
    await chatDocsAccordion.evaluate((el) => {
      el.open = true;
    });
  }
  await shot(page, "chat");

  // Documents live in an accordion on the project workspace page itself,
  // not a standalone route -- capture the Internal Knowledge Base project
  // (3 seeded documents) with the accordion forced open.
  const kbSlug = String(demo.knowledgeBase.name)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-");
  await page.goto(`${BASE_URL}/projects/${kbSlug}/`);
  const documentsAccordion = page.locator(".documents-accordion");
  if (await documentsAccordion.count()) {
    await documentsAccordion.evaluate((el) => {
      el.open = true;
    });
  }
  await shot(page, "documents");

  const contentSlug = String(demo.content.name)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-");
  await page.goto(`${BASE_URL}/workflows/?project=${contentSlug}`);
  await shot(page, "workflows");

  await page.goto(`${BASE_URL}/executions/`);
  await shot(page, "executions");

  await page.goto(`${BASE_URL}/providers/`);
  await shot(page, "providers");

  await page.goto(`${BASE_URL}/guide/`);
  await shot(page, "guideline");

  await page.goto(`${BASE_URL}/settings/`);
  await shot(page, "docs");

  await browser.close();
  console.log(`\nDone. Screenshots written to ${OUT_DIR}`);
  console.log("Demo data was left in place for repeat runs -- delete the");
  console.log(
    `"${demo.support.name}" / "${demo.content.name}" / "${demo.knowledgeBase.name}" projects manually if you don't want them kept.`,
  );
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
