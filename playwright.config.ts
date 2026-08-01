import fs from "fs";
import path from "path";
import { defineConfig, devices } from "@playwright/test";
import { env, getEnvironment } from "./tests/e2e/helpers/env";

// Auto-load local env files so every project (chromium/firefox/webkit/mobile)
// picks up credentials consistently, regardless of what happens to be
// exported in the invoking shell. CI should keep setting real env vars /
// secrets directly — these files are gitignored and won't exist there.
// Node's loadEnvFile never overrides a variable already in process.env, so
// load in priority order: `.env.e2e.local` first (highest priority), then
// `.env` filling in anything still missing.
for (const file of [".env.e2e.local", ".env"]) {
  const fullPath = path.join(__dirname, file);
  if (fs.existsSync(fullPath)) {
    process.loadEnvFile(fullPath);
  }
}

const environment = getEnvironment();
const isCI = !!process.env.CI;

/**
 * E2E_ENVIRONMENT controls the target (local | test | staging | production-smoke).
 * Production is never the default — see tests/e2e/helpers/env.ts.
 */
export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: isCI,
  retries: isCI ? 2 : 0,
  workers: environment === "production-smoke" ? 1 : isCI ? 4 : undefined,
  timeout: 30_000,
  expect: { timeout: 10_000 },
  reporter: [
    ["html", { open: "never", outputFolder: "playwright-report" }],
    ["list"],
    ...(isCI
      ? [
          ["junit", { outputFile: "test-results/junit.xml" }] as const,
          // Each CI job's blob report gets uploaded as an artifact and
          // merged into one public HTML report across jobs -- see the
          // publish-report job in the e2e-* workflows.
          ["blob", { outputDir: "blob-report" }] as const,
        ]
      : []),
  ],
  outputDir: "test-results",

  use: {
    baseURL: env.baseUrl(),
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    navigationTimeout: 15_000,
    actionTimeout: 10_000,
  },

  projects: [
    // --- Authentication setup projects (run first, produce storage state) ---
    {
      name: "setup-user",
      testMatch: /auth\.setup\.ts/,
    },

    // --- Chromium: full suite ---
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], storageState: "playwright/.auth/primary-user.json" },
      dependencies: ["setup-user"],
      testIgnore: [/production-smoke\//, /auth\.setup\.ts/],
    },

    // --- Firefox / WebKit: critical + regression only, run on main/nightly ---
    {
      name: "firefox",
      use: { ...devices["Desktop Firefox"], storageState: "playwright/.auth/primary-user.json" },
      dependencies: ["setup-user"],
      testIgnore: [/production-smoke\//, /auth\.setup\.ts/],
      grep: /@critical|@regression/,
    },
    {
      name: "webkit",
      use: { ...devices["Desktop Safari"], storageState: "playwright/.auth/primary-user.json" },
      dependencies: ["setup-user"],
      testIgnore: [/production-smoke\//, /auth\.setup\.ts/],
      grep: /@critical|@regression/,
    },

    // --- Mobile viewport: critical navigation + auth only ---
    {
      name: "mobile-chrome",
      use: { ...devices["Pixel 7"], storageState: "playwright/.auth/primary-user.json" },
      dependencies: ["setup-user"],
      testMatch: /(navigation|auth)\/.*\.spec\.ts/,
      testIgnore: /auth\.setup\.ts/,
      grep: /@critical/,
    },

    // --- Production smoke: Chromium only, no auth-setup dependency (logs in inline) ---
    {
      name: "production-smoke",
      use: { ...devices["Desktop Chrome"], baseURL: env.baseUrl() },
      testMatch: /production-smoke\//,
    },
  ],
});
