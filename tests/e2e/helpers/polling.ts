import { Locator, expect } from "@playwright/test";

export class PollingTimeoutError extends Error {
  constructor(message: string, public readonly lastObservedState: string) {
    super(message);
    this.name = "PollingTimeoutError";
  }
}

/**
 * Polls a locator's text against a set of terminal states with a bounded
 * timeout, so async Celery/document/workflow processing never hangs a test
 * indefinitely and never relies on arbitrary sleeps.
 */
export async function waitForStatusText(
  locator: Locator,
  terminalStates: RegExp,
  options: { timeoutMs?: number; label?: string } = {}
): Promise<string> {
  const timeoutMs = options.timeoutMs ?? 120_000;
  const label = options.label ?? "status";
  let lastObserved = "(never observed)";

  try {
    await expect(locator).toHaveText(terminalStates, { timeout: timeoutMs });
    lastObserved = (await locator.textContent()) ?? lastObserved;
    return lastObserved;
  } catch (err) {
    lastObserved = (await locator.textContent().catch(() => null)) ?? lastObserved;
    throw new PollingTimeoutError(
      `Timed out after ${timeoutMs}ms waiting for ${label} to reach a terminal state. Last observed: "${lastObserved}"`,
      lastObserved
    );
  }
}

/**
 * Polls a backend API resource via a getter function until a predicate on
 * the returned status field is satisfied, or the timeout elapses.
 */
export async function pollApiUntil<T>(
  fetcher: () => Promise<T>,
  predicate: (result: T) => boolean,
  options: { timeoutMs?: number; intervalMs?: number; label?: string } = {}
): Promise<T> {
  const timeoutMs = options.timeoutMs ?? 120_000;
  const intervalMs = options.intervalMs ?? 2_000;
  const label = options.label ?? "resource";
  const deadline = Date.now() + timeoutMs;
  let last: T | undefined;

  while (Date.now() < deadline) {
    last = await fetcher();
    if (predicate(last)) return last;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  throw new PollingTimeoutError(
    `Timed out after ${timeoutMs}ms polling ${label}. Last observed: ${JSON.stringify(last)}`,
    JSON.stringify(last)
  );
}
