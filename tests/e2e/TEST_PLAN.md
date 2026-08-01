# E2E Test Plan — AI Automation Platform

This document is the source of truth for what the Playwright suite covers,
what it does not, and why. It was written after inspecting the actual
repositories (`ai-platform-backend` FastAPI app and `ai-platform-frontend`
Django app), not from assumptions. See "Architecture discovered" in the
final delivery summary for the full route inventory.

## Scope and non-goals

- This suite validates **frontend + backend integration behavior** through
  the Django UI, plus direct FastAPI contract tests. It is not a security
  penetration test, not a load test, and passing it is not a claim that the
  application is bug-free — it proves the specific behaviors listed below.
- Real LLM provider calls happen server-side in FastAPI. Playwright cannot
  intercept that network hop from the browser. The primary chat suite uses a
  **frontend-level mock** (intercepting the Django HTMX response) — tagged
  `@mocked-frontend-only` — which validates the UI contract but not the real
  Django → FastAPI → provider round trip. See "Known gaps" below.

## Traceability matrix

Legend — Status: ✅ implemented · 🚧 partially implemented · ⬜ not implemented (gap, see notes).

| Feature           | User journey                                                                                           | API dependency                                               | Test type                  | Browser coverage               | Destructive         | Status                                                                                                                                   |
| ----------------- | ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------ | -------------------------- | ------------------------------ | ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | --- | ------------------------------------------------------------------------------------------------------------------- |
| Public pages      | Homepage, login, register load                                                                         | `GET /` (frontend)                                           | E2E                        | chromium/firefox/webkit/mobile | No                  | ✅                                                                                                                                       |
| Navigation        | Favicon, 404, protected redirect                                                                       | frontend routes                                              | E2E                        | chromium/firefox/webkit        | No                  | ✅                                                                                                                                       |
| Health            | Frontend `/health/`, backend `/health`                                                                 | both                                                         | E2E + API                  | chromium                       | No                  | ✅                                                                                                                                       |
| Auth              | Register (success/invalid/duplicate)                                                                   | `POST /auth/register`                                        | E2E + API                  | chromium                       | Yes (creates users) | ✅                                                                                                                                       |
| Auth              | Login (success/wrong password/unknown user)                                                            | `POST /auth/login`                                           | E2E + API                  | chromium/firefox/webkit        | No                  | ✅                                                                                                                                       |
| Auth              | Logout, protected-route redirect                                                                       | frontend session                                             | E2E                        | chromium                       | No                  | ✅                                                                                                                                       |
| Auth              | Token refresh                                                                                          | `POST /auth/refresh`                                         | API                        | —                              | No                  | ✅                                                                                                                                       |
| Auth              | Multiple isolated users / cross-user access                                                            | `GET /auth/me` + resource routes                             | E2E + API                  | chromium                       | No                  | ✅                                                                                                                                       |
| Auth              | Google OAuth real flow                                                                                 | `POST /auth/google`                                          | —                          | —                              | —                   | ⬜ (explicitly out of scope per plan; see Known gaps)                                                                                    |
| Auth              | Expired/invalid session token                                                                          | JWT expiry                                                   | API                        | —                              | No                  | 🚧 (invalid-token case covered; expiry requires a short-lived test token, not exercised)                                                 |
| Projects          | Create, list, open                                                                                     | `POST/GET /projects`                                         | E2E + API                  | chromium/firefox/webkit        | Yes                 | ✅                                                                                                                                       |
| Projects          | Update/rename, validation                                                                              | `PATCH /projects/{id}`                                       | E2E                        | chromium                       | Yes                 | ✅                                                                                                                                       |
| Projects          | Delete, deleted-project navigation                                                                     | `DELETE /projects/{id}`                                      | E2E                        | chromium                       | Yes                 | ✅                                                                                                                                       |
| Projects          | Cancelled deletion leaves project intact                                                               | —                                                            | —                          | —                              | —                   | ⬜ (no confirm dialog on project delete in current UI — see Known gaps)                                                                  |
| Projects          | Ownership isolation                                                                                    | cross-user `GET/DELETE`                                      | E2E + API                  | chromium                       | No                  | ✅                                                                                                                                       |
| Projects          | Empty/multiple-project states                                                                          | —                                                            | E2E                        | chromium                       | No                  | ✅ (empty-state assertion is conditional; see test comment)                                                                              |
| Chats             | Create, rename, delete                                                                                 | `POST/PATCH/DELETE /chats`                                   | E2E                        | chromium                       | Yes                 | ✅ (rename not yet covered — see gap)                                                                                                    |
| Chats             | Send message, response render, reload persistence                                                      | `POST /chats/{id}/messages`                                  | E2E (mocked-frontend-only) | chromium                       | Yes                 | 🚧                                                                                                                                       |
| Chats             | Streaming state, regenerate                                                                            | `POST .../messages/stream`, `.../regenerate`                 | —                          | —                              | —                   | ⬜ (not implemented — see Known gaps)                                                                                                    |
| Chats             | Empty message rejected, provider failure surfaced                                                      | client validation / mocked 5xx                               | E2E                        | chromium                       | Yes                 | ✅                                                                                                                                       |
| Chats             | Ownership isolation                                                                                    | cross-user chat access                                       | E2E                        | chromium                       | No                  | ✅                                                                                                                                       |
| Chats             | Rapid double-submit dedup                                                                              | —                                                            | E2E (mocked-frontend-only) | chromium                       | Yes                 | ✅                                                                                                                                       |
| Chats             | Switching chats does not mix messages                                                                  | frontend routes                                              | E2E                        | chromium                       | No                  | ✅                                                                                                                                       |
| Documents         | Upload supported types, status polling to terminal state                                               | `POST /projects/{id}/documents`, `GET /documents/{id}`       | E2E + API                  | chromium                       | Yes                 | ✅                                                                                                                                       |
| Documents         | Invalid extension / malformed / empty file handling                                                    | extension allowlist in extractors                            | E2E                        | chromium                       | Yes                 | ✅                                                                                                                                       |
| Documents         | Oversized file                                                                                         | in-memory generated fixture                                  | E2E                        | chromium                       | Yes                 | ✅ (backend enforcement behavior not independently confirmed — see Known gaps)                                                           |
| Documents         | Delete document                                                                                        | `DELETE /documents/{id}`                                     | E2E                        | chromium                       | Yes                 | ✅                                                                                                                                       |
| Documents         | Retry/cancel processing                                                                                | `.../process/retry`, `.../process/cancel`                    | —                          | —                              | —                   | ⬜ (Phase 2 gap — needs a controllable slow/failing processor)                                                                           |
| Documents         | Chunk inspection / RAG retrieval                                                                       | `GET /documents/{id}/chunks`, `POST /projects/{id}/retrieve` | API                        | —                              | No                  | 🚧 (chunks covered conditionally; retrieval endpoint not covered)                                                                        |
| Documents         | Ownership isolation                                                                                    | cross-user document access                                   | API                        | —                              | No                  | ✅                                                                                                                                       |
| Workflows         | Create, add step, save, reload persistence                                                             | `POST /projects/{id}/workflows`, `.../steps`                 | E2E + API                  | chromium                       | Yes                 | ✅                                                                                                                                       |
| Workflows         | Invalid configuration rejected                                                                         | validation                                                   | E2E + API                  | chromium                       | No                  | ✅                                                                                                                                       |
| Workflows         | Run, queued/running/completed/failed                                                                   | `POST /workflows/{id}/run`, `GET /runs/{id}`                 | E2E + API                  | chromium                       | Yes                 | ✅                                                                                                                                       |
| Workflows         | Cancel, retry, resume                                                                                  | `POST /runs/{id}/cancel                                      | retry                      | resume`                        | E2E + API           | chromium                                                                                                                                 | Yes | 🚧 (endpoints exercised; exact state-machine transitions not asserted in detail — timing-dependent, see Known gaps) |
| Workflows         | Delete workflow                                                                                        | `DELETE /workflows/{id}`                                     | E2E                        | chromium                       | Yes                 | ✅                                                                                                                                       |
| Workflows         | DAG dependency (`depends_on`) and `condition` branch metadata render                                   | `POST .../steps` with `depends_on`/`condition`               | E2E                        | chromium                       | Yes                 | ✅ (drag-to-reorder UI itself doesn't exist in the current builder — steps are ordered by `step_order` input, not covered further)       |
| Workflows         | Ownership isolation                                                                                    | cross-user workflow access                                   | API                        | —                              | No                  | ✅                                                                                                                                       |
| Executions        | Run history list, execution detail                                                                     | `GET /runs`, `GET /runs/{id}`                                | E2E                        | chromium                       | No                  | ✅                                                                                                                                       |
| Executions        | Cancelled-execution deletion with confirm dialog                                                       | `window.confirm` + `DELETE /runs/canceled`                   | E2E                        | chromium                       | Yes                 | ✅                                                                                                                                       |
| Executions        | Generic renderer: JSON/array/null/large/unknown-field payloads                                         | `GET /runs/{id}`                                             | —                          | —                              | —                   | ⬜ (Phase 2 gap — needs seeded runs with specific output shapes)                                                                         |
| Providers         | List, defaults, health check                                                                           | `GET /providers`, `/providers/config`, `/{provider}/health`  | E2E + API                  | chromium                       | No                  | ✅                                                                                                                                       |
| Providers         | Secret values never rendered                                                                           | api_key input                                                | E2E + API                  | chromium                       | No                  | ✅                                                                                                                                       |
| Providers         | Invalid settings rejected                                                                              | client-side required fields                                  | E2E                        | chromium                       | No                  | ✅                                                                                                                                       |
| Providers         | User-scoped isolation                                                                                  | —                                                            | —                          | —                              | —                   | ⬜ (provider config in this app is project/global-scoped, not user-scoped — see backend `provider_config.py`; not applicable as written) |
| Security          | Invalid/missing token, cross-user object refs, server-side validation                                  | various                                                      | E2E + API                  | chromium                       | No                  | ✅                                                                                                                                       |
| Security          | Open redirect prevention                                                                               | `next=` param                                                | E2E                        | chromium                       | No                  | ✅                                                                                                                                       |
| Security          | CSRF on Django forms/HTMX                                                                              | Django CSRF middleware                                       | —                          | —                              | —                   | ⬜ (Phase 2 gap — requires a controlled CSRF-token-stripped request)                                                                     |
| HTMX              | Document status polling attributes appear while active, disappear once terminal                        | `hx-trigger="every 3s"` on `document_status.html`            | E2E                        | chromium                       | Yes                 | ✅                                                                                                                                       |
| HTMX              | Back/forward navigation across project pages                                                           | frontend routes                                              | E2E                        | chromium                       | No                  | ✅                                                                                                                                       |
| HTMX              | Out-of-band swaps                                                                                      | —                                                            | —                          | —                              | —                   | ⬜ (no OOB swap usage found in the templates inspected — not applicable as built, see Known gaps)                                        |
| Visual regression | Login, register, project list (empty + populated), providers, workflows, executions                    | —                                                            | Visual                     | chromium only                  | No                  | ✅ (scaffolded and implemented; no baselines are committed yet — see Known gaps)                                                         |
| Accessibility     | axe-core scan of login/register/projects/chat/workflows/executions/providers; full keyboard-only login | `@axe-core/playwright`                                       | E2E                        | chromium/firefox/webkit/mobile | No                  | ✅ (automated scan only — see Known gaps for what this does not certify)                                                                 |
| Mobile            | Critical navigation + auth                                                                             | —                                                            | E2E                        | mobile-chrome                  | No                  | ✅ (project config in place; scoped to `navigation/` + `auth/` critical tests)                                                           |
| Production smoke  | Public pages, health, smoke-account login/logout                                                       | —                                                            | E2E                        | chromium                       | No                  | ✅                                                                                                                                       |
| Production smoke  | Controlled writes (`prod-smoke-*`)                                                                     | opt-in                                                       | E2E                        | chromium                       | Opt-in only         | ✅                                                                                                                                       |

## Known gaps and why

1. **Real-provider integration is not exercised by the primary suite.** The
   backend's provider abstraction (`app/services/ai/providers/*`) has no
   test/mock mode exposed via an env var. True black-box mocking would
   require either (a) a backend-side `MOCK_PROVIDER=true` flag routing to a
   deterministic fake provider, or (b) an actual local Ollama instance in the
   test docker-compose. Neither exists today. The suite instead: uses a
   frontend-level route mock for the primary suite (`@mocked-frontend-only`),
   and defines an optional, disabled-by-default real-provider smoke test
   (`@real-provider`) for a small, cost-bounded sanity check. Recommend
   adding a backend mock-provider mode as follow-up work.
2. **No project-delete confirmation dialog exists in the current UI** — the
   "cancelled deletion leaves data intact" scenario from the plan doesn't
   apply to projects as built (it does apply to execution deletion, which
   uses `window.confirm` and is covered).
3. **Workflow DAG coverage is metadata-level, not a visual DAG builder.**
   `depends_on`/`condition` render/persist correctly (covered), but the
   current UI has no drag-to-reorder or graph view to test — steps are
   ordered by a plain `step_order` number input. Condition _evaluation_
   during a real run (does `previous.length > 0` actually skip a step?) is
   not asserted — that requires a deterministic provider response to
   verify branching outcome, tracked as a further gap.
4. **Execution-detail generic renderer edge cases** (large output, null
   values, unknown fields) need seeded runs with specific crafted output,
   which requires either backend fixtures or a mock step. Deferred to Phase 2.
5. **CSRF is not exercised.** No test sends a request with a stripped/invalid
   CSRF token to confirm Django's middleware rejects it — deferred, since it
   requires deliberately bypassing the browser's normal form submission.
6. **HTMX out-of-band swap is not tested.** One does exist —
   `app_base.html`'s `<div id="flash-stack" hx-swap-oob="true">` — but the
   HTMX-driven fragment endpoints inspected (`document_status_partial`,
   `execution_status_partial`, `execution_content_partial`) are plain
   `hx-get` polling partials that don't appear to emit a matching
   `flash-stack` element, and the chat composer's own `hx-post` is
   superseded by its JS fetch/SSE handling (see `provider-mock.ts`) rather
   than a real htmx-driven submit. No fragment response that actually
   exercises this OOB swap was confirmed, so a targeted test wasn't written
   rather than guessing at one — flagged here as a genuine open question,
   not asserted as "not applicable."
7. **Visual regression has no committed baselines yet.** Screenshots are
   environment-specific (fonts/rendering differ by OS), so baselines must be
   generated once on the same runner image nightly CI uses, not locally —
   see `.github/workflows/e2e-nightly.yml`'s `visual-regression` job for the
   exact bootstrap command (`--update-snapshots`). Until that's run once and
   committed, every `@visual` test will fail on its first real run — that is
   expected, not a bug in the tests.
8. **Accessibility scanning is `axe-core` only, not a certification.** It
   catches programmatically detectable issues (missing labels, contrast,
   heading order, ARIA misuse) but cannot verify subjective usability,
   correct focus order through complex custom widgets, or actual
   screen-reader phrasing/announcements. Only one flow (login) has an
   explicit full keyboard-only walkthrough; the rest rely on axe-core's
   `keyboard`-related rules rather than a manual tab-order test per page.
9. **Google OAuth** is intentionally not automated with real Google
   credentials, per instruction — only the application-side initiation
   (`login/google/`) could be smoke-tested for redirect behavior, and even
   that is deferred since it depends on `GOOGLE_CLIENT_ID` being configured
   in the target environment.
10. **Selectors were derived from static template inspection**, not a running
    app. Run `npx playwright test --list` and the critical suite once against
    a real local environment before relying on this suite as a CI gate —
    template text can drift from what was read here.

## Priority status

- **Phase 1 (release-blocking, this delivery): implemented.** Health, auth,
  project CRUD, chat basic flow (mocked), document upload/processing,
  workflow create/run/inspect, ownership checks, production-safe smoke, CI
  wiring, failure artifacts.
- **Phase 2 (regression): mostly implemented.** Validation/error paths,
  cancel/retry/resume, cross-browser critical subset, provider settings,
  duplicate-submit/chat-switch races, workflow DAG metadata, HTMX polling
  lifecycle + back/forward navigation, visual regression (chromium,
  baselines not yet committed — see Known gaps), and axe-core accessibility
  scanning are all in. CSRF, the flash-stack OOB swap, and condition
  _evaluation_ during a real run remain gaps tracked above.
- **Phase 3 (extended assurance): not implemented.** Real-provider smoke is
  scaffolded as an opt-in tag but disabled by default; performance
  baselines, larger documents, network degradation, and rollback
  verification are not covered.
