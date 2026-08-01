# E2E / API / Smoke Test Suite

Playwright Test (TypeScript) suite covering the Django frontend and FastAPI
backend of the AI Automation Platform. Start with
[TEST_PLAN.md](./TEST_PLAN.md) for what's covered, what isn't, and why.

## Layout

```
tests/
  e2e/
    auth/            login, registration, logout, security
    projects/        project CRUD + ownership
    chats/           chat flow (mocked provider)
    documents/       upload/processing/deletion
    workflows/       workflow create/run/inspect
    executions/      run history + execution detail
    providers/       provider settings
    navigation/      public pages, health, console/network cleanliness
    accessibility/   axe-core scans + keyboard-only login
    visual/          screenshot regression (chromium only, no baselines committed yet)
    production-smoke/ non-destructive checks only, @production-safe
    fixtures/        base test (diagnostics + API clients), auth setup
    helpers/         env, api-client, polling, provider-mock, fixture-files
    test-data/       small.txt/md/csv/json/pdf, invalid-extension.exe, malformed.pdf
    auth.setup.ts    logs in via UI, saves storage state for reuse
    TEST_PLAN.md
  api/
    auth/ projects/ documents/ workflows/ health/   direct FastAPI contract tests
playwright.config.ts
scripts/test-e2e.sh   local stack runner (up/down)
```

## Environment variables

Required for any run:

| Variable                                                   | Purpose                                                                              |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `E2E_ENVIRONMENT`                                          | `local` \| `test` \| `staging` \| `production-smoke`. Never defaults to production.  |
| `E2E_BASE_URL`                                             | Django frontend base URL (default `http://localhost:8001`)                           |
| `E2E_API_URL`                                              | FastAPI backend base URL (default `http://localhost:8000`)                           |
| `E2E_USER_EMAIL` / `E2E_USER_PASSWORD`                     | Primary dedicated e2e-user account                                                   |
| `E2E_SECONDARY_USER_EMAIL` / `E2E_SECONDARY_USER_PASSWORD` | Secondary account, used for ownership/isolation tests                                |
| `PROD_SMOKE_EMAIL` / `PROD_SMOKE_PASSWORD`                 | Dedicated production smoke account (never a real user's)                             |
| `ALLOW_PRODUCTION_SMOKE_WRITES`                            | `true` to enable the opt-in `prod-smoke-*` write/cleanup test. Defaults to disabled. |

None of these are committed. Populate a local `.env` (already gitignored)
or export them in your shell / CI secrets.

## Running locally

```bash
npm ci
npx playwright install --with-deps

# Bring up Postgres/Redis/Celery worker (backend repo's docker compose),
# FastAPI, Django, run migrations, and seed the two e2e accounts:
./scripts/test-e2e.sh up

npx playwright test --list          # sanity-check the suite loads
npx playwright test --grep @critical
npx playwright test --grep @smoke
npx playwright test --grep @api
npx playwright test                 # full suite

./scripts/test-e2e.sh down
```

`scripts/test-e2e.sh` assumes `ai-platform-backend` is a sibling directory
(the workspace layout in the root `CLAUDE.md`). Override with
`E2E_BACKEND_DIR=/path/to/backend`.

## Tags

| Tag                     | Meaning                                                                |
| ----------------------- | ---------------------------------------------------------------------- |
| `@smoke`                | Fast, high-value subset                                                |
| `@critical`             | Release-blocking — must pass before deploy                             |
| `@regression`           | Broader coverage, run on main/nightly                                  |
| `@api`                  | Direct backend API test (no browser UI)                                |
| `@visual`               | Screenshot comparison — chromium only, see "Visual regression" below   |
| `@accessibility`        | axe-core scan or keyboard-only walkthrough — see "Known gaps" for scope |
| `@destructive`          | Writes/deletes data — refused automatically against `production-smoke` |
| `@production-safe`      | Explicitly non-destructive — the only tests the prod-smoke CI job runs |
| `@real-provider`        | Calls a real configured AI provider — disabled by default, opt-in only |
| `@mocked-frontend-only` | Uses the frontend-level provider mock (see Known gaps in TEST_PLAN.md) |
| `@slow`                 | Long-running (workflow execution, document processing)                 |

```bash
npx playwright test --grep @smoke
npx playwright test --grep @critical
npx playwright test --grep @production-safe
npx playwright test --grep-invert @real-provider
```

## Production smoke

```bash
E2E_ENVIRONMENT=production-smoke \
E2E_BASE_URL=https://<production-frontend> \
E2E_API_URL=https://<production-backend> \
PROD_SMOKE_EMAIL=... PROD_SMOKE_PASSWORD=... \
npx playwright test --grep @production-safe --project=production-smoke
```

Any test not tagged `@production-safe` is refused automatically when
`E2E_ENVIRONMENT=production-smoke` (see `tests/e2e/fixtures/base.ts` and
`tests/e2e/helpers/env.ts::assertNotDestructiveInProduction`).

## Visual regression

`@visual` tests compare screenshots and are environment-sensitive (fonts and
rendering differ by OS), so they only run on a single controlled browser
(chromium) and are excluded from the PR/main gates — see the
`visual-regression` job in `.github/workflows/e2e-nightly.yml`.

No baselines are committed yet. Before the first real comparison run,
generate them **on the same environment nightly CI uses** (do this in CI via
`workflow_dispatch`, or in a matching container locally — a baseline
generated on your Mac will not match Linux CI rendering):

```bash
npm run test:e2e:visual:update
```

Commit the resulting `tests/e2e/visual/**/*-snapshots/` directories. Until
that's done, every `@visual` test fails on its first assertion — expected,
not a bug.

## Accessibility

`@accessibility` tests use `@axe-core/playwright` to scan for WCAG 2 A/AA
violations on each critical page, plus one full keyboard-only walkthrough of
login. This is an automated floor, not an accessibility certification — see
"Known gaps" in [TEST_PLAN.md](./TEST_PLAN.md) for exactly what it does and
doesn't verify.

```bash
npm run test:e2e:accessibility
```

## Extending the suite

- New domain area → new folder under `tests/e2e/<area>/`, import `test`/`expect`
  from `tests/e2e/fixtures/base` (not `@playwright/test` directly) to get
  console/network diagnostics and the authenticated API clients.
- New backend contract → `tests/api/<area>/`.
- Selector priority: `getByRole` → `getByLabel` → `getByPlaceholder` →
  `getByText` → `getByTestId`. Avoid CSS class / DOM-position selectors.
  The frontend has no `data-testid` convention yet — most current specs use
  labels, placeholders, role+name, and a few stable existing attributes
  (`data-document-row`, `data-execution-status`, etc.). Add `data-testid`
  to a template only when none of the above work reliably.
- New async/polling wait → use `helpers/polling.ts` (`waitForStatusText` for
  a DOM status badge, `pollApiUntil` for a backend field), never
  `page.waitForTimeout()`.
- All generated test data must be named `e2e-<timestamp>-w<worker>-<random>`
  (or `prod-smoke-*` in production) via `helpers/env.ts::runId` /
  `helpers/test-data.ts::uniqueName`, and cleaned up via the API client even
  if the test fails (see `primaryApi`/`secondaryApi` fixture teardown).

## Known gaps

See "Known gaps and why" in [TEST_PLAN.md](./TEST_PLAN.md). Headline items:
real AI provider calls aren't exercised end-to-end (backend has no mock-mode
flag yet); visual regression has no committed baselines yet (see above);
axe-core accessibility scanning is automated-only, not a certification; CSRF
enforcement and the app's one HTMX out-of-band swap (`#flash-stack`) aren't
exercised; Google OAuth is not automated with real credentials.
