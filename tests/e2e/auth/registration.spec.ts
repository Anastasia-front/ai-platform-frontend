import { expect, test } from "../fixtures/base";
import { runId } from "../helpers/env";

test.use({ storageState: { cookies: [], origins: [] } });

test.describe("Registration @critical", () => {
  test("successful registration then login @smoke", async ({
    page,
  }, testInfo) => {
    const email = `${runId(testInfo.workerIndex)}@example.com`;
    const password = "Str0ng!Passw0rd";

    await page.goto("/register/");
    await page.getByLabel("Email").fill(email);
    await page.locator('input[name="password"]').fill(password);
    await page.getByRole("button", { name: /register/i }).click();

    await expect(page).toHaveURL(/\/login\//);
    await expect(page.locator(".flash")).toContainText(/account created/i);

    await page.getByLabel("Email").fill(email);
    await page.locator('input[name="password"]').fill(password);
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page).toHaveURL(/\/projects\//);
  });

  test("password not meeting policy is rejected client-side", async ({
    page,
  }, testInfo) => {
    const email = `${runId(testInfo.workerIndex)}@example.com`;
    await page.goto("/register/");
    await page.getByLabel("Email").fill(email);
    const passwordInput = page.getByLabel("Password", { exact: true });
    await passwordInput.fill("weak");
    await page.getByRole("button", { name: /register/i }).click();
    // HTML5 constraint validation (minlength/pattern) blocks submission client-side.
    await expect(page).toHaveURL(/\/register\//);
    const isValid = await passwordInput.evaluate((el: HTMLInputElement) =>
      el.checkValidity(),
    );
    expect(isValid).toBe(false);
  });

  test("duplicate registration is rejected with a clear error", async ({
    page,
  }) => {
    // Re-registering the already-provisioned primary e2e user must fail,
    // proving server-side validation isn't bypassable via the form.
    const { env } = await import("../helpers/env");
    await page.goto("/register/");
    await page.getByLabel("Email").fill(env.userEmail());
    await page.getByLabel("Password", { exact: true }).fill("Str0ng!Passw0rd");
    await page.getByRole("button", { name: /register/i }).click();
    await expect(page).toHaveURL(/\/register\//);
    await expect(page.locator(".flash.error, .flash")).toBeVisible();
  });

  test("invalid email format is rejected client-side", async ({ page }) => {
    await page.goto("/register/");
    const emailInput = page.getByLabel("Email");
    await emailInput.fill("not-an-email");
    await page.getByLabel("Password", { exact: true }).fill("Str0ng!Passw0rd");
    await page.getByRole("button", { name: /register/i }).click();
    await expect(page).toHaveURL(/\/register\//);
    const isValid = await emailInput.evaluate((el: HTMLInputElement) =>
      el.checkValidity(),
    );
    expect(isValid).toBe(false);
  });
});
