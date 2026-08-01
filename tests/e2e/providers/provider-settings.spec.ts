import { test, expect } from "../fixtures/base";

test.describe("Provider settings @critical", () => {
  test("provider list loads with chat and embedding sections @smoke", async ({ page }) => {
    await page.goto("/providers/");
    await expect(page.getByRole("heading", { name: "Providers", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Chat Providers" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Embedding Providers" })).toBeVisible();
  });

  test("secret API key values are never rendered back to the browser @regression", async ({ page }) => {
    await page.goto("/providers/");
    const html = await page.content();
    // The api_key input is `type=password` and only ever shows a placeholder
    // ("Saved. Leave blank to keep current key.") — its value attribute must
    // never contain an actual secret.
    const apiKeyInputs = page.locator('input[name="api_key"]');
    const count = await apiKeyInputs.count();
    for (let i = 0; i < count; i++) {
      await expect(apiKeyInputs.nth(i)).toHaveAttribute("type", "password");
      const value = await apiKeyInputs.nth(i).inputValue();
      expect(value).toBe("");
    }
    expect(html).not.toMatch(/sk-[a-zA-Z0-9]{20,}/);
  });

  test("invalid chat defaults (missing model) are rejected", async ({ page }) => {
    await page.goto("/providers/");
    const modelInput = page.locator('[data-model-input]').first();
    await modelInput.fill("");
    await page.getByRole("button", { name: "Save Chat Defaults" }).click();
    const isValid = await modelInput.evaluate((el: HTMLInputElement) => el.checkValidity());
    expect(isValid).toBe(false);
  });

  test("provider health check renders a status without crashing @regression @slow", async ({ page }) => {
    await page.goto("/providers/");
    const checkButton = page.getByRole("button", { name: "Check" }).first();
    if (await checkButton.isVisible().catch(() => false)) {
      // This submits a form that synchronously calls the real configured
      // provider (Ollama) for a health round trip — can legitimately exceed
      // the global actionTimeout, independent of app correctness.
      await checkButton.click({ timeout: 60_000 });
      await expect(page.locator("body")).not.toContainText(/traceback|internal server error/i);
    }
  });
});
