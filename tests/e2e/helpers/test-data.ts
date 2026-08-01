import { test as base } from "@playwright/test";
import { runId } from "./env";

export function uniqueName(kind: string, workerIndex: number): string {
  return `${runId(workerIndex)}-${kind}`;
}

/** Resources created by a test, tracked so cleanup always runs even on failure. */
export class ResourceTracker {
  private projectIds: (string | number)[] = [];

  trackProject(id: string | number) {
    this.projectIds.push(id);
  }

  async cleanup(deleteProject: (id: string | number) => Promise<void>) {
    for (const id of this.projectIds.splice(0)) {
      await deleteProject(id).catch(() => {
        // Best-effort cleanup: a resource already deleted by the test itself
        // (e.g. a delete-project test) is not a cleanup failure.
      });
    }
  }
}

export const test = base;
