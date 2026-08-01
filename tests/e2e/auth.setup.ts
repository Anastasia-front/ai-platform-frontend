import { expect, test as setup } from "@playwright/test";
import { env } from "./helpers/env";

const primaryState = "playwright/.auth/primary-user.json";
const secondaryState = "playwright/.auth/secondary-user.json";

async function attemptLogin(page: import("@playwright/test").Page, email: string, password: string) {
  await page.goto("/login/");
  await page.getByLabel("Email").fill(email);
  await page.locator('input[name="password"]').fill(password);
  await page.getByRole("button", { name: "Log in" }).click();
  await page.waitForLoadState("networkidle");
}

async function registerAccount(page: import("@playwright/test").Page, email: string, password: string) {
  await page.goto("/register/");
  await page.getByLabel("Email").fill(email);
  const passwordInput = page.locator('input[name="password"]');
  await passwordInput.fill(password);

  // The register form enforces its password policy (min 6 chars, one
  // uppercase, one digit, one special char) via HTML5 pattern/minlength.
  // Surface that clearly instead of letting the click silently no-op.
  const isValid = await passwordInput.evaluate((el: HTMLInputElement) => el.checkValidity());
  if (!isValid) {
    throw new Error(
      `The password for ${email} does not satisfy the register form's policy ` +
        "(min 6 chars, one uppercase letter, one digit, one special character). " +
        "Update it in your .env.e2e.local."
    );
  }

  await page.getByRole("button", { name: /register/i }).click();
  await page.waitForLoadState("networkidle");
}

/**
 * Logs in as the given e2e user, auto-provisioning the account via the
 * register form first if it doesn't exist yet in this environment's DB.
 * This makes the suite self-bootstrapping against a freshly seeded/empty
 * test database — no manual pre-registration step required.
 */
async function loginAndSaveState(
  page: import("@playwright/test").Page,
  email: string,
  password: string,
  statePath: string,
) {
  await attemptLogin(page, email, password);

  if (/\/login\/$/.test(page.url())) {
    await registerAccount(page, email, password);
    await attemptLogin(page, email, password);
  }

  // A successful login must leave the login form and land on an authenticated
  // page — if this breaks, every downstream test would fail opaquely, so we
  // assert it explicitly here with a clear failure message.
  await expect(
    page,
    `Login as ${email} did not redirect away from /login/ after login (and, if needed, ` +
      "auto-registration) — check credentials, account state, or login flow changes",
  ).not.toHaveURL(/\/login\/$/, { timeout: 10_000 });

  await page.context().storageState({ path: statePath });
}

setup("authenticate as primary e2e user", async ({ page }) => {
  await loginAndSaveState(
    page,
    env.userEmail(),
    env.userPassword(),
    primaryState,
  );
});

setup("authenticate as secondary e2e user", async ({ page }) => {
  await loginAndSaveState(
    page,
    env.secondaryUserEmail(),
    env.secondaryUserPassword(),
    secondaryState,
  );
});
