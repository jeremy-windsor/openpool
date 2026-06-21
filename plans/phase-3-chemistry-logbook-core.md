# Phase 3 - Chemistry and Logbook Core

Date: 2026-06-07

## Decision

Phase 3 finishes the required pool-care core before we spend time on sharing,
multi-user behavior, public exposure, or Home Assistant integrations.

The priority is:

```text
accurate math -> useful dosing -> durable history -> pilot feedback
```

Full authentication is not part of this phase. The app stays LAN/VPN-only.
Sharing remains read-only and optional. Multi-user support stays out of scope.

## Phase Goal

OpenPool should be useful as a real pool logbook and calculator for a pilot:

- Enter readings.
- Calculate common chemical adjustments.
- Log what was added.
- Track maintenance events.
- Review history without losing context.
- Export the useful records.
- Trust the math because formulas, assumptions, and tests are visible.

## Non-Goals

- Public exposure.
- Full authentication.
- Multi-user accounts or roles.
- Home Assistant, MQTT, or nodejs-poolController write integrations.
- Automatic dosing or closed-loop control.
- A large UI redesign.
- Charts before the underlying history is complete.
- Metric UI conversion until the core formulas and US-unit workflow are stable.

Metric support still matters for v1. Do not design formula code in a way that
blocks it. Store and label units explicitly, but do not mix full metric
conversion into this phase unless the chemistry slice is already done.

## Build Slices

### 3A - Logbook Integrity

Purpose: make the existing records correctable and complete.

- Add edit and delete workflows for readings.
- Add edit and delete workflows for chemical additions.
- Add maintenance event API endpoints.
- Add maintenance event UI.
- Add maintenance event CSV export.
- Keep confirmation simple. No modal circus.
- Preserve UTC storage and pool-local display.
- Add tests for create, edit, delete, export, and invalid inputs.

Acceptance:

- A bad reading can be corrected from the UI.
- A bad chemical addition can be corrected from the UI.
- Maintenance work can be logged and exported.
- History shows readings, additions, and maintenance in one usable timeline or
  clearly grouped sections.

### 3B - Calcium and Total Alkalinity

Purpose: finish the first missing required dosing formulas.

- Implement calcium hardness raise:
  - calcium chloride
  - calcium chloride dihydrate
- Implement total alkalinity raise:
  - sodium bicarbonate / baking soda
- Add formula docs in `docs/formulas.md`.
- Add public-reference fixtures.
- Add unit tests before wiring the UI.
- Add calculator goals and result cards.
- Add one-click "log this dose" into chemical additions.

Acceptance:

- Calculator can recommend CH and TA raise doses with source notes,
  assumptions, warnings, confidence, and labeled units.
- Doses can be logged without retyping the amount.

### 3C - CSI

Purpose: give the dashboard a useful scale/corrosion signal without pretending
the number is perfect.

- Implement CSI from pH, TA, CH, CYA, temperature, salt, and borates where
  available.
- Document the formula and correction assumptions.
- Store computed CSI on readings.
- Recompute CSI when a reading is edited.
- Show CSI on dashboard/history as approximate.
- Add warnings when inputs are missing or the result is low-confidence.

Acceptance:

- New readings with enough inputs get CSI automatically.
- Dashboard shows CSI status and plain-language meaning.
- Missing inputs do not create fake precision.

### 3D - Acid/Base and Chemical Side Effects

Purpose: stop treating chemicals as isolated knobs.

- Add muriatic acid / pH lowering guidance.
- Add pH raising guidance with appropriate uncertainty.
- Add side-effect modeling for:
  - trichlor
  - dichlor
  - cal-hypo
  - acid
- Show expected side effects in calculator results.
- Store expected side effects with logged doses if the schema needs it.
- Add warnings where the chemistry is process-based instead of a clean one-shot
  dose.

Acceptance:

- The calculator can explain that a chemical changes more than one reading.
- Acid/pH guidance is marked approximate and does not fake lab-grade certainty.

### 3E - Operational Helpers

Purpose: cover real-world pool operations that are annoying to calculate by
hand.

- SLAM helper flow:
  - choose target profile
  - use FC/CYA shock target
  - warn about high-FC pH testing
  - support repeated logging
- Dilution/refill model:
  - estimate reduction for CYA, salt, CH, borates
  - make it clear this is proportional replacement math
- SWG runtime estimate:
  - pool volume
  - cell output
  - desired FC/day
  - runtime percent or hours

Acceptance:

- The app can guide the owner through the most common non-maintenance
  scenarios without needing a separate calculator.

### 3F - Pilot Polish

Purpose: make the chemistry/logbook core usable enough to run against a real
pool for a few weeks.

- Update history view for the new record types.
- Add filters that matter: date range and record type.
- Make export names predictable.
- Review mobile form ergonomics after the new fields exist.
- Tighten dashboard wording around "target" vs "typical range".
- Add pilot checklist to `docs/deployment.md` or a dedicated pilot note.

Acceptance:

- A pilot user can run day-to-day pool logging from the app.
- The exported data is enough to recover or inspect the pilot history.
- Known missing features are documented instead of rediscovered.

## Data Model Notes

Existing tables already cover much of this phase:

- `test_readings`
- `chemical_additions`
- `maintenance_events`
- `pool_profiles`

Likely schema additions to consider only when needed:

- `chemical_additions.expected_effects_json`
- `chemical_additions.calculation_json`
- `pool_settings_history`
- `target_profiles`
- `test_readings.calculated_at` if recalculation history becomes important

Do not add tables just because they sound architectural. Add them when the
feature needs durable history or when export/restore would otherwise lose
important context.

## Testing Rules

- Formula docs and fixtures come before UI wiring.
- Every new calculator goal gets unit tests and at least one public-reference
  fixture.
- Every new write flow gets route tests.
- Every export gets a regression test.
- Keep the GitHub Actions test gate before Docker publishing.

Useful commands:

```bash
uv run ruff check .
uv run pytest -q
git diff --check
```

## Security Rules

- Keep the app LAN/VPN-only.
- No public exposure before authentication exists.
- Do not add automatic dosing.
- Do not commit real pool history, private IPs, share tokens, or deployment
  secrets.
- Share JSON remains read-only.

## Done Means

Phase 3 is done when:

- Readings, additions, and maintenance records can be created, edited, deleted,
  listed, and exported.
- Required chemistry helpers from the math plan are implemented or explicitly
  deferred with a reason.
- Doses can be logged from calculator results.
- Dashboard/recommendation wording matches the actual confidence of the math.
- Tests pass locally and in GitHub Actions.
- The GHCR image builds after the test gate.
- The project tracker is updated with what changed, what was tested, and what
  remains.
