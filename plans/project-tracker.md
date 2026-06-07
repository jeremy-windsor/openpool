# OpenPool Project Tracker

Date started: 2026-06-07

This tracker exists so future chats do not keep asking the same questions. Keep
it current when a phase starts or finishes, when a decision changes, or when a
feature is deliberately moved out of scope.

Do not put secrets, real share tokens, private deployment details, or real pool
history in this file.

## Current Snapshot

- Repo: `openpool`
- Product: local-first Docker-hosted pool chemistry logbook and calculator.
- Current commit at tracker creation: `c4aa4538296c`
- Primary image: `ghcr.io/jeremy-windsor/openpool:latest`
- Deployment posture: localhost, SSH tunnel, VPN, or trusted LAN only.
- Current phase: Phase 3 - Chemistry and Logbook Core.

## Standing Decisions

- Use `openpool` as the repo, Docker image, and Python package slug.
- Style as "OpenPool" in user-facing text when useful.
- Keep storage local-first with SQLite.
- Keep one container with a mounted `/data` directory.
- Keep GHCR as the primary image registry for now.
- Keep the app LAN/VPN-only until authentication exists.
- Do not build automatic dosing or closed-loop chemical control.
- Do not build multi-user support yet.
- Do not build Home Assistant/MQTT/nodejs-poolController write integrations
  until the standalone app works.
- Prefer boring server-rendered FastAPI/Jinja pages over a SPA.
- Add tests before expanding chemistry formulas.
- Every formula needs inputs, units, assumptions, source notes, and tests.

## Read

- `AGENTS.md` - repo operating instructions.
- `README.md` - current run/test/deploy summary.
- `plans/openpool-plan.md` - product and architecture plan.
- `plans/math-plan.md` - chemistry formula plan.
- `plans/ui-design-plan.md` - UI and mobile design plan.
- `plans/next-steps.md` - active handoff summary.
- `docs/formulas.md` - implemented formula notes.
- `docs/review-notes.md` - security and adversarial review notes.
- `docs/deployment.md` - deployment guidance.
- `docs/api.md` - API documentation.

## Built

### Phase 1 - Runnable MVP

- FastAPI package under `openpool/`.
- SQLite-backed data store.
- Dockerfile and compose files.
- GHCR Docker publishing workflow.
- Health and version endpoints.
- Dashboard, reading form, addition form, history, calculator, settings, and
  share page.
- API endpoints for pools, readings, additions, calculator, share JSON, CSV
  export, and JSON backup.
- Initial chemistry:
  - liquid chlorine / FC raise
  - dry stabilizer / CYA raise
  - salt raise
  - FC/CYA targets
- Formula result metadata:
  - source note
  - assumptions
  - warnings
  - confidence
- Timezone handling:
  - UTC storage
  - pool-local display
  - configurable default timezone
- Basic security guardrails:
  - localhost compose bind
  - disabled share by default
  - share token required when enabled
  - no share token echo in pool API responses
  - cross-origin write rejection
  - CSV formula-injection escaping
  - service worker avoids stale chemistry HTML

### Phase 1-2 Finalization

- Committed `tests/` suite for chemistry, SQLite persistence, and FastAPI
  routes.
- Added public reference fixtures under `tests/fixtures/`.
- Added GitHub Actions test job with `ruff check` and `pytest`.
- Made Docker image build depend on the test job.
- Fixed SQLite thread handling for async page-route form writes.
- Added dashboard/share reading status tiles.
- Updated README and review notes.

## Tested

- Local route/form tests passed in the committed test suite.
- GitHub Actions Docker workflow passed for commit `c4aa4538296c`.
- GHCR image publishes only after the test job passes.
- Earlier Docker-hosted smoke test verified:
  - `/api/health`
  - `/api/version`
  - dashboard rendering
  - timezone display
  - calculator metadata
  - disabled share endpoint returning `403`

## Current Requirements

Phase 3 focuses on required pool-care features:

- Finish pool math and chemistry helpers.
- Add useful dosing outputs.
- Let calculator doses be logged as chemical additions.
- Complete add/edit/delete/history storage for readings, additions, and
  maintenance events.
- Keep exports useful enough for backup and inspection.

## Moved Later

- Full authentication.
- Multi-user accounts and roles.
- Public exposure.
- Home Assistant/MQTT/nodejs-poolController integrations beyond read-only share
  JSON.
- Charts/trends.
- Full metric UI conversion.
- Import/restore.
- Offline write queue.
- Docker Hub publishing unless there is a concrete reason.

## Removed Or Avoided

- Browser LocalStorage as primary data store.
- Public-by-default networking.
- Automatic chemical dosing.
- Copying proprietary calculator code, assets, or private APIs.
- SPA framework churn for the initial app.

## Active Concerns

- Dashboard wording currently risks calling generic ranges "targets". Tighten
  this in Phase 3.
- Share tokens are plaintext in SQLite until auth/secrets handling exists.
- Write APIs are open to any trusted-LAN client that can reach the app.
- Metric support is stored as a preference but not implemented through inputs,
  results, exports, or charts.
- Maintenance events table exists, but API/UI/export are not built yet.

## Next Phase

See `plans/phase-3-chemistry-logbook-core.md`.

Start with logbook integrity and dose logging, then add chemistry in tested
slices:

1. Edit/delete readings and additions.
2. Maintenance events API/UI/export.
3. Calcium and TA dosing.
4. CSI.
5. Acid/base and side effects.
6. SLAM, dilution/refill, and SWG runtime helpers.
7. Pilot polish and deployment checklist.

## How To Update This Tracker

When work starts:

- Add the phase or task under Current Requirements if it is not already there.
- Add any new settled decision under Standing Decisions.

When work finishes:

- Add user-visible features under Built.
- Add verification under Tested.
- Move deferred work under Moved Later with the reason.
- Update Active Concerns if a risk was fixed or discovered.
- Update the current commit if this file is being changed as part of a commit.
