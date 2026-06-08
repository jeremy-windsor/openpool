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

## UI Build Status

The design spec is `plans/ui-design-plan.md` (Calm Aquatic). This section tracks
how much of that spec is actually implemented in `templates/` and `static/`, so
future chats do not rediscover the gap. Frontend-only work is owned by the UI
chats; backend/logic stays with the main build.

Legend: [x] built · [~] partial/placeholder · [ ] not built.

### Slice 1 - Global shell + dashboard (done)

- [x] Design tokens completed in `tokens.css` (shadows, input/sm radii, easing).
- [x] Top bar: brand mark, theme toggle, settings icon (dev "Health" link removed
  from primary nav).
- [x] Bottom tab nav with inline SVG icons + raised center "Add" FAB.
- [x] Theme toggle: Light -> Dark -> Outdoor, persisted in localStorage, no-flash
  head script, `?theme=` URL override for share/iframe/testing.
- [x] StatusBanner with status icon + plain-language verdict.
- [x] RecommendationCard with icon + "Log this dose" action.
- [x] ReadingTile + RangeBar (marker position by status: low/in/high band).
- [x] Pool-local timestamps humanized client-side ("Today, 5:02 PM").
- [x] Chemical/unit names prettified in display.
- [x] "Log this dose" prefills the addition form client-side from query params
  (no backend round-trip).
- Verified by headless screenshots: mobile + desktop (light), dark, outdoor,
  prefilled addition form. 32/32 tests pass.

### Pending UI slices

- [ ] Add-reading form: StepperInputs, "from last test" seeding, non-blocking
  inline validation, "More tests" disclosure, results screen after save.
- [ ] Calculator: goal chips, DoseResultCard, ConfidenceBadge, side-effects panel.
- [ ] History: segmented Readings/Additions/Maintenance, date-range filters,
  mobile StackedRow vs desktop table.
- [ ] Settings: grouped sections, theme picker in-page, volume helper, units.
- [ ] Share page: chrome-free, iframe-safe styling pass.
- [ ] Trends/charts (after history is complete).
- [ ] EmptyState/Loading/Error states across all data views.
- [ ] Exact RangeBar marker positioning would benefit from numeric low/high on
  tiles (small `services.reading_tiles` change) - deferred, coordinate first.

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
