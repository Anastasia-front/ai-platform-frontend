import { test as diagnosticsTest, expect } from "./diagnostics";
import { BackendApiClient } from "../helpers/api-client";
import { env, assertNotDestructiveInProduction } from "../helpers/env";

interface ApiFixtures {
  primaryApi: BackendApiClient;
  secondaryApi: BackendApiClient;
}

/**
 * Base fixture merging console/network diagnostics with authenticated
 * backend API clients for setup and cleanup. Domain specs should import
 * `test`/`expect` from this file rather than "@playwright/test" directly.
 */
diagnosticsTest.beforeEach(async ({}, testInfo) => {
  const titlePath = testInfo.titlePath.join(" > ");

  // Belt-and-suspenders guard: even if a test is mistakenly run against
  // production-smoke, any test not explicitly tagged @production-safe is
  // treated as destructive and refused. See helpers/env.ts.
  const isProductionSafe = titlePath.includes("@production-safe");
  assertNotDestructiveInProduction({ destructive: !isProductionSafe });

  // @slow tests poll document/workflow processing to a terminal state,
  // which can take well past the global 30s test timeout (playwright.config.ts).
  // Centralized here so individual specs don't need testInfo.setTimeout().
  if (titlePath.includes("@slow")) {
    testInfo.setTimeout(180_000);
  }
});

export const test = diagnosticsTest.extend<ApiFixtures>({
  primaryApi: async ({}, use) => {
    const client = await BackendApiClient.login(
      env.userEmail(),
      env.userPassword(),
    );
    await use(client);
    await client.dispose();
  },
  secondaryApi: async ({}, use) => {
    const client = await BackendApiClient.login(
      env.secondaryUserEmail(),
      env.secondaryUserPassword(),
    );
    await use(client);
    await client.dispose();
  },
});

export { expect };
