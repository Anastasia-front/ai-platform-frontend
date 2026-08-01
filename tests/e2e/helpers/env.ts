/**
 * Central place for reading E2E environment configuration.
 * Never defaults to production — an explicit E2E_ENVIRONMENT must be set.
 */

export type E2eEnvironment = "local" | "test" | "staging" | "production-smoke";

const VALID_ENVIRONMENTS: E2eEnvironment[] = [
  "local",
  "test",
  "staging",
  "production-smoke",
];

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(
      `Missing required environment variable ${name}. See tests/e2e/README.md for the full list.`,
    );
  }
  return value;
}

export function getEnvironment(): E2eEnvironment {
  const raw = process.env.E2E_ENVIRONMENT ?? "local";
  if (!VALID_ENVIRONMENTS.includes(raw as E2eEnvironment)) {
    throw new Error(
      `Invalid E2E_ENVIRONMENT="${raw}". Must be one of: ${VALID_ENVIRONMENTS.join(", ")}`,
    );
  }
  return raw as E2eEnvironment;
}

export function isProductionSmoke(): boolean {
  return getEnvironment() === "production-smoke";
}

export function assertNotDestructiveInProduction(testMetadata: {
  destructive: boolean;
}): void {
  if (isProductionSmoke() && testMetadata.destructive) {
    throw new Error(
      "Destructive E2E tests cannot run against production. " +
        "Tag this test @production-safe only if it performs no writes, " +
        "or gate it behind ALLOW_PRODUCTION_SMOKE_WRITES with a prod-smoke-* prefixed resource.",
    );
  }
}

export function allowProductionSmokeWrites(): boolean {
  return (
    isProductionSmoke() && process.env.ALLOW_PRODUCTION_SMOKE_WRITES === "true"
  );
}

export const env = {
  baseUrl: () => process.env.E2E_BASE_URL || "http://localhost:8001",
  apiUrl: () => process.env.E2E_API_URL || "http://localhost:8000",

  userEmail: () => requireEnv("E2E_USER_EMAIL"),
  userPassword: () => requireEnv("E2E_USER_PASSWORD"),

  secondaryUserEmail: () => requireEnv("E2E_SECONDARY_USER_EMAIL"),
  secondaryUserPassword: () => requireEnv("E2E_SECONDARY_USER_PASSWORD"),

  prodSmokeEmail: () => requireEnv("PROD_SMOKE_EMAIL"),
  prodSmokePassword: () => requireEnv("PROD_SMOKE_PASSWORD"),
};

/** Unique, recognizable identifier for any resource this run creates. */
export function runId(workerIndex: number): string {
  const random = Math.random().toString(36).slice(2, 8);
  const prefix = isProductionSmoke() ? "prod-smoke" : "e2e";
  return `${prefix}-${Date.now()}-w${workerIndex}-${random}`;
}
