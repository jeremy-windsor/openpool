# OpenPool Next Steps

Date: 2026-06-07

This is the handoff note for the next implementation chat. The repo has moved
from planning-only to an early runnable MVP with committed tests and a gated
GHCR image build. The next work should finish the required chemistry, dosing,
and logbook core before adding sharing, multi-user behavior, or public
exposure.

## Current State

`main` is synced with GitHub at:

```text
c4aa4538296c Finalize Phase 1-2: commit tests, gate CI on them, fix sqlite threading, add dashboard target tiles
```

The GHCR image is built and published by GitHub Actions:

```text
ghcr.io/jeremy-windsor/openpool:latest
```

The app has been smoke-tested in a Docker-hosted test deployment. Keep that
deployment LAN/VPN-only until authentication exists.

## What Was Built

- FastAPI application package under `openpool/`.
- SQLite-backed local data store.
- Dockerfile, local compose file, and GHCR compose file.
- GitHub Actions Docker workflow.
- `/api/health` and `/api/version` build metadata endpoints.
- Server-rendered pages:
  - dashboard
  - new reading
  - new chemical addition
  - history
  - calculator
  - settings
  - read-only share page
- API endpoints for:
  - pools
  - readings
  - additions
  - calculator
  - share JSON
  - readings CSV export
  - additions CSV export
  - all-data JSON export
- Initial chemistry helpers for:
  - liquid chlorine / FC raise
  - dry stabilizer / CYA raise
  - salt raise
  - FC/CYA target lookup
- Formula output now includes source note, assumptions, warnings, and confidence.
- Pool timezone handling:
  - `OPENPOOL_TIMEZONE` config for new default pools.
  - `datetime-local` form input is normalized to UTC using pool timezone.
  - reading/addition display uses pool local time.
- Basic security guardrails:
  - compose binds to `127.0.0.1` by default.
  - share endpoints are disabled by default.
  - share token is required when sharing is enabled.
  - pool API responses do not echo share tokens or private pool notes.
  - simple cross-origin write rejection middleware.
  - CSV formula-injection escaping.
  - service worker does not serve stale cached dashboard chemistry while offline.

## Live Smoke Test Results

Verified against the test deployment after pulling the GHCR image:

- `/api/health` returned OK.
- `/api/version` reported build SHA `271777184f5791cc778cf97245682caa56f351a4`.
- Dashboard rendered latest reading and recommendation.
- Reading and addition timestamps displayed in pool local time.
- Calculator returned the expected liquid chlorine dose with formula metadata.
- Disabled share endpoint returned `403`.

Temporary smoke-test data was added to the test deployment:

- one reading with note `codex live smoke test`
- one liquid chlorine addition with reason `codex live smoke test`

Do not assume that test data belongs in examples, docs, exports, or fixtures.

## Known Gaps

### Test and CI

Done (Phase 1-2 finalization):

- Committed suite under `tests/`: chemistry (with public reference fixtures in
  `tests/fixtures/public_reference_examples.json`), SQLite persistence, and
  FastAPI route tests. 32 tests passing.
- GitHub Actions now runs `ruff check` and `pytest` in a `test` job; the image
  `build` job `needs: test`, so a red suite blocks publishing.
- Ruff is clean (`B008` is ignored as the FastAPI `Depends()` idiom).
- Fixed a real bug found by the route tests: async page routes
  (`save_reading`, `save_addition`, `save_settings`) received their SQLite
  connection from a threadpool dependency but ran on the event-loop thread, so
  `check_same_thread=True` raised. `db.connect` now uses
  `check_same_thread=False` (each request still has its own connection).

Still open:

- No type checking (mypy/pyright) in CI yet.
- `.codex-local-tests/` scratch coverage is superseded by `tests/` and can be
  removed when convenient.

### Security

- No real authentication yet.
- Write APIs are open to any client that can reach the service.
- Share tokens are stored plaintext in SQLite.
- No rate limiting.
- No secure cookie/session story.
- App is suitable only for localhost, SSH tunnel, VPN, or trusted LAN testing.

Do not add public exposure before auth and proxy guidance are designed. Full
auth is not part of the next phase; the app stays LAN/VPN-only.

### Product Features

- Readings and additions can be created, but not edited/deleted from the UI.
- Maintenance events table exists, but there is no API/UI/export flow.
- `pool_settings_history` and target profile history are not implemented.
- Multi-pool support is skeletal; the data model has `pool_id`, but the UI does
  not expose pool switching yet.
- Metric support is only a stored preference. Inputs/results still behave like
  US units.
- Trends/charts are not built.
- Import/restore flows are not built.
- Home Assistant/MQTT/nodejs-poolController integration is not built beyond the
  share JSON foundation.
- Offline PWA support is minimal; no offline-write queue.

### Chemistry

Implemented:

- units helpers
- liquid chlorine
- CYA/stabilizer
- salt
- FC/CYA targets

Still missing from the math plan:

- calcium hardness dosing
- total alkalinity / baking soda dosing
- borates dosing
- CSI
- muriatic acid / pH lowering
- pH raising guidance
- chemical side effects:
  - trichlor
  - dichlor
  - cal-hypo
  - acid
- SLAM helper flow
- dilution/refill model
- SWG runtime estimate

## Recommended Next Build Order

The active next phase is documented in
[`phase-3-chemistry-logbook-core.md`](phase-3-chemistry-logbook-core.md).
The durable tracker is
[`project-tracker.md`](project-tracker.md).

1. **Finish logbook integrity**
   - Edit reading.
   - Delete reading with confirmation.
   - Edit addition.
   - Delete addition with confirmation.
   - Add "log this dose" from calculator result to chemical additions.

2. **Add maintenance events**
   - API endpoints.
   - UI form.
   - History tab/section or timeline.
   - CSV export.

3. **Add calcium and TA chemistry**
   - Calcium chloride dose.
   - Calcium chloride dihydrate dose.
   - Baking soda / TA raise.
   - Formula docs and tests first.

4. **Add CSI**
   - Implement only after TA/CH inputs and corrections are stable.
   - Include warnings and confidence language.
   - Show CSI on dashboard with clear “approximate” behavior.

5. **Add acid/base, side effects, and operational helpers**
   - Muriatic acid / pH lowering guidance.
   - pH raising guidance.
   - Side effects for trichlor, dichlor, cal-hypo, and acid.
   - SLAM helper.
   - Dilution/refill model.
   - SWG runtime estimate.

6. **Pilot polish**
   - Tighten dashboard wording around target vs typical range.
   - Make history/export useful with the new record types.
   - Document pilot verification.

Later:

- Authentication before any public exposure.
- Target profiles/settings history after the core chemistry is usable, unless
  SLAM helper work needs a minimal profile model sooner.
- Trends/charts after enough history exists.
- Metric support after formula behavior is stable.
- Import/restore after exports settle.

## Useful Verification Commands

Local no-install checks:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m compileall -q openpool
git diff --check
```

After dependencies are installed:

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
```

Docker image path:

```bash
docker compose -f docker-compose.ghcr.yml pull
docker compose -f docker-compose.ghcr.yml up -d
curl http://127.0.0.1:5280/api/health
curl http://127.0.0.1:5280/api/version
```

## Guardrails for the Next Chat

- Keep repo changes small and boring.
- Add tests before expanding chemistry.
- Do not expose the app publicly before auth.
- Do not commit real pool history, real tokens, IPs, or private deployment
  details.
- Keep GHCR as the primary image registry unless Docker Hub has a concrete
  reason.
- Preserve the local-first SQLite design.
