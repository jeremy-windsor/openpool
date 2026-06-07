# OpenPool Next Steps

Date: 2026-06-07

This is the handoff note for the next implementation chat. The repo has moved
from planning-only to an early runnable MVP. The next work should harden the
foundation before piling on chemistry and UI features.

## Current State

`main` is synced with GitHub at:

```text
2717771 Expose build metadata
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

- No committed test suite yet.
- Local scratch tests exist under `.codex-local-tests/`, intentionally ignored
  from git per the previous task instruction.
- GitHub Actions currently builds/publishes Docker images but does not run
  Python tests, route tests, lint, or type checks.

This is the next thing to fix. Chemistry without committed tests is a rake
collection.

### Security

- No real authentication yet.
- Write APIs are open to any client that can reach the service.
- Share tokens are stored plaintext in SQLite.
- No rate limiting.
- No secure cookie/session story.
- App is suitable only for localhost, SSH tunnel, VPN, or trusted LAN testing.

Do not add public exposure before auth and proxy guidance are designed.

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

1. **Promote tests into the repo**
   - Add `tests/` with formula tests and API/route smoke tests.
   - Move useful `.codex-local-tests/` coverage into committed tests.
   - Add golden fixture JSON for public reference chemistry cases.
   - Update GitHub Actions so Docker publishing depends on tests passing.

2. **Add edit/delete workflows**
   - Edit reading.
   - Delete reading with confirmation.
   - Edit addition.
   - Delete addition with confirmation.
   - Keep the UI simple; no modal circus.

3. **Add maintenance events**
   - API endpoints.
   - UI form.
   - History tab/section.
   - CSV export.

4. **Add target profiles and settings history**
   - Maintenance, SLAM/shock, spa profiles.
   - Persist settings changes in `pool_settings_history`.
   - Make dashboard/recommendations use active target profile.

5. **Add calcium and TA chemistry**
   - Calcium chloride dose.
   - Calcium chloride dihydrate dose.
   - Baking soda / TA raise.
   - Formula docs and tests first.

6. **Add CSI**
   - Implement only after TA/CH inputs and corrections are stable.
   - Include warnings and confidence language.
   - Show CSI on dashboard with clear “approximate” behavior.

7. **Add trends**
   - Chart latest history for FC, pH, TA, CH, CYA, salt, CSI, water temp.
   - Add table fallback for accessibility.
   - Add chemical addition markers.

8. **Add authentication**
   - Optional single-user password.
   - Session/cookie handling.
   - Reverse-proxy guidance.
   - Only then consider any broader exposure than trusted LAN/VPN.

9. **Add metric support**
   - Decide canonical DB units.
   - Convert inputs, results, exports, and charts at the edges.
   - Add tests for conversion and display behavior.

10. **Add import/restore**
    - Readings CSV import.
    - Additions CSV import.
    - JSON backup restore.
    - Dry-run validation before writing.

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

