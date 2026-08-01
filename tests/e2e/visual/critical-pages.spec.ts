import { expect, test } from "../fixtures/base";
import { uniqueName } from "../helpers/test-data";

/**
 * Visual regression on a small, deliberately narrow set of stable pages
 * (per the test plan: "do not make every page a screenshot test"). Runs
 * separately from the critical functional gate — see README "Tags" (@visual)
 * and the nightly/main CI workflows, which are the only ones that execute it.
 *
 * Baselines are environment-specific (fonts/rendering vary by OS). Generate
 * them once per environment with:
 *   npx playwright test --grep @visual --update-snapshots
 * and commit the resulting `*-snapshots/` directory for that CI image.
 *
 * Every authenticated page shares the same sidebar, which lists every
 * project on the account — a masked *row* still lets the *count* of items
 * change and reflow the whole page around it. Masking the entire sidebar
 * (and other shared-account list containers) instead avoids that, since
 * this suite runs against the same shared e2e-user account as the rest of
 * the functional suite and can't assume it's empty at comparison time.
 *
 * The mask must cover the whole `<aside class="sidebar">` (app_base.html),
 * not just `.sidebar-section` — `.sidebar` also contains `.utility-nav`,
 * whose links get focus/visited styling and can reflow independently.
 * Likewise the executions page's whole `.execution-console` (filter tabs,
 * "Total executions" count, and list) needs masking, not just the list
 * itself — those other pieces change too as other suites/workers run
 * concurrently against the same account.
 */
const SIDEBAR = ".sidebar";

test.describe("Visual regression @visual", () => {
  test.use({
    storageState: { cookies: [], origins: [] },
    viewport: { width: 1280, height: 800 },
  });

  test("login page", async ({ page }) => {
    await page.goto("/login/");
    await expect(page).toHaveScreenshot("login.png", {
      maxDiffPixelRatio: 0.02,
    });
  });

  test("register page", async ({ page }) => {
    await page.goto("/register/");
    await expect(page).toHaveScreenshot("register.png", {
      maxDiffPixelRatio: 0.02,
    });
  });
});

test.describe("Visual regression (authenticated) @visual", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test("empty projects state", async ({ page, primaryApi }, testInfo) => {
    // Only meaningful when the account genuinely has no projects; this is
    // the same conditional pattern used in project-crud.spec.ts.
    await page.goto("/projects/");
    const emptyState = page.locator(".empty-state", {
      hasText: "No projects yet",
    });
    test.skip(
      !(await emptyState.isVisible().catch(() => false)),
      "Shared account currently has projects — empty state not reachable without deleting them",
    );
    await expect(page).toHaveScreenshot("projects-empty.png", {
      maxDiffPixelRatio: 0.02,
      mask: [page.locator(SIDEBAR)],
    });
  });

  test("project list with one project", async ({
    page,
    primaryApi,
  }, testInfo) => {
    const project = await primaryApi.createProject(
      uniqueName("visual-project", testInfo.workerIndex),
    );
    await page.goto("/projects/");
    await expect(page).toHaveScreenshot("projects-list.png", {
      maxDiffPixelRatio: 0.02,
      mask: [page.locator(SIDEBAR), page.locator(".project-grid")],
    });
    await primaryApi.deleteProject(project.id);
  });

  test("providers page", async ({ page }) => {
    await page.goto("/providers/");
    await expect(page).toHaveScreenshot("providers.png", {
      maxDiffPixelRatio: 0.02,
      mask: [page.locator(SIDEBAR)],
    });
  });

  test("workflows page (no project selected)", async ({ page }) => {
    await page.goto("/workflows/");
    await expect(page).toHaveScreenshot("workflows-empty.png", {
      maxDiffPixelRatio: 0.02,
      mask: [page.locator(SIDEBAR), page.locator(".project-tabs")],
    });
  });

  test("executions empty/list state", async ({ page }) => {
    await page.goto("/executions/");
    await expect(page).toHaveScreenshot("executions.png", {
      maxDiffPixelRatio: 0.02,
      mask: [page.locator(SIDEBAR), page.locator(".execution-console")],
    });
  });
});
