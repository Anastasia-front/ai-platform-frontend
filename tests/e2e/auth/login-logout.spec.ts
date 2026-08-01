import { expect, test } from "../fixtures/base";
import { env } from "../helpers/env";

test.use({ storageState: { cookies: [], origins: [] } });

test.describe("Login and logout @critical", () => {
  test("successful login redirects to projects @smoke @production-safe", async ({
    page,
  }) => {
    await page.goto("/login/");
    await page.getByLabel("Email").fill(env.userEmail());
    await page.getByLabel("Password", { exact: true }).fill(env.userPassword());
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page).toHaveURL(/\/projects\//);
  });

  test("incorrect password shows an error and stays on login", async ({
    page,
  }) => {
    await page.goto("/login/");
    await page.getByLabel("Email").fill(env.userEmail());
    await page
      .getByLabel("Password", { exact: true })
      .fill("definitely-wrong-password-123!");
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page).toHaveURL(/\/login\//);
    await expect(page.locator(".flash.error, .flash")).toBeVisible();
  });

  test("unknown account shows an error and stays on login", async ({
    page,
  }) => {
    await page.goto("/login/");
    await page
      .getByLabel("Email")
      .fill(`no-such-user-${Date.now()}@example.com`);
    await page.getByLabel("Password", { exact: true }).fill("SomePassword123!");
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page).toHaveURL(/\/login\//);
    await expect(page.locator(".flash.error, .flash")).toBeVisible();
  });

  test("password field is not prefilled after a failed attempt", async ({
    page,
  }) => {
    await page.goto("/login/");
    await page.getByLabel("Email").fill(env.userEmail());
    await page.getByLabel("Password", { exact: true }).fill("wrong-password");
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page).toHaveURL(/\/login\//);
    await expect(page.getByLabel("Password", { exact: true })).toHaveValue("");
  });

  test("logout ends the session and protected pages redirect to login @smoke @production-safe", async ({
    page,
  }) => {
    await page.goto("/login/");
    await page.getByLabel("Email").fill(env.userEmail());
    await page.getByLabel("Password", { exact: true }).fill(env.userPassword());
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page).toHaveURL(/\/projects\//);

    await page.goto("/logout/");
    await expect(page).toHaveURL(/\/login\//);

    await page.goto("/projects/");
    await expect(page).toHaveURL(/\/login\//);
  });

  test("next= redirect returns to the originally requested page after login", async ({
    page,
  }) => {
    await page.goto("/projects/");
    await expect(page).toHaveURL(/\/login\/\?next=/);
    await page.getByLabel("Email").fill(env.userEmail());
    await page.getByLabel("Password", { exact: true }).fill(env.userPassword());
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page).toHaveURL(/\/projects\//);
  });
});
