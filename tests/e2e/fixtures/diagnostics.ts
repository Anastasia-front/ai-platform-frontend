import { test as base, expect, Page } from "@playwright/test";

export interface DiagnosticsFixture {
  consoleErrors: string[];
  failedRequests: { url: string; status: number }[];
}

/**
 * Narrow allowlist for documented, harmless third-party noise.
 * Do NOT add app-origin errors here — only add entries with a comment
 * explaining why the noise is known-harmless and third-party.
 */
const CONSOLE_ALLOWLIST: RegExp[] = [
  /ResizeObserver loop limit exceeded/, // benign browser layout notice, not app-caused
];

const NETWORK_STATUS_ALLOWLIST: RegExp[] = [
  /\/favicon\.ico$/, // some browsers probe this even when favicon.svg is used
];

export const test = base.extend<{ diagnostics: DiagnosticsFixture }>({
  diagnostics: async ({ page }: { page: Page }, use) => {
    const consoleErrors: string[] = [];
    const failedRequests: { url: string; status: number }[] = [];

    const onConsole = (msg: import("@playwright/test").ConsoleMessage) => {
      if (msg.type() !== "error") return;
      const text = msg.text();
      if (CONSOLE_ALLOWLIST.some((re) => re.test(text))) return;
      consoleErrors.push(text);
    };
    const onPageError = (err: Error) => {
      consoleErrors.push(`Uncaught: ${err.message}`);
    };
    const onResponse = (res: import("@playwright/test").Response) => {
      const url = res.url();
      if (res.status() < 500) return;
      if (NETWORK_STATUS_ALLOWLIST.some((re) => re.test(url))) return;
      failedRequests.push({ url, status: res.status() });
    };

    page.on("console", onConsole);
    page.on("pageerror", onPageError);
    page.on("response", onResponse);

    await use({ consoleErrors, failedRequests });

    page.off("console", onConsole);
    page.off("pageerror", onPageError);
    page.off("response", onResponse);
  },
});

/** Call at the end of a test to assert no unexpected console/5xx noise occurred. */
export function assertNoUnexpectedErrors(diagnostics: DiagnosticsFixture) {
  expect(diagnostics.consoleErrors, "unexpected browser console errors").toEqual([]);
  expect(diagnostics.failedRequests, "unexpected first-party 5xx responses").toEqual([]);
}

export { expect };
