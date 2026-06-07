# openpool plan

## Decision

Build **openpool**: a local-first, Docker-hosted pool chemistry logbook and calculator with SQLite storage, a mobile-friendly web app, CSV/JSON export, and optional exports to Home Assistant and nodejs-poolController.

> **Name:** the slug is `openpool` (one word) — used for the repo, Docker image,
> and Python package (import names can't contain hyphens, so `open-pool` is out).
> It may be styled "OpenPool" in UI/branding, but the identifier stays `openpool`.

The useful product is simple:

```text
settings -> readings -> calculations -> history -> export
```

Everything else should subscribe to that clean local source of truth.

## Companion plans

- [`math-plan.md`](math-plan.md) — the chemistry engine: formulas, units,
  validation fixtures, build order.
- [`ui-design-plan.md`](ui-design-plan.md) — the design system: visual language,
  navigation, page-by-page UX, components, accessibility, offline/PWA, and the
  design-to-build phasing. **Read this before building any page** — this plan
  lists pages, that plan specifies how they look and behave.

## Goals

1. **Local-first storage**
   - SQLite database stored in a Docker volume.
   - No required cloud account.
   - No browser LocalStorage as primary truth.
   - Easy backup by copying the SQLite file or using built-in JSON/CSV export.

2. **Transparent pool chemistry calculator**
   - Implement calculations from first principles and public pool-care methodology.
   - Do not copy proprietary app code, assets, or private APIs.
   - Validate formulas against public references and known chemistry identities.

3. **Historical tracking**
   - Store test readings over time.
   - Store chemical additions over time.
   - Store maintenance events.
   - Store pool setting/target changes.
   - Show tables and charts.

4. **Mobile-friendly app**
   - Fast poolside entry from a phone browser.
   - Large controls.
   - No login required for trusted LAN deployments.
   - Optional authentication/token controls before any public exposure.

5. **Portable exports**
   - CSV export for readings and additions.
   - JSON export for backups and integrations.
   - Read-only share endpoint similar in spirit to hosted pool apps.
   - Home Assistant-friendly REST/MQTT output.
   - nodejs-poolController/dashPanel-friendly JSON endpoint.

6. **Safe scope**
   - Calculator, logbook, dashboard, and exports only.
   - No automatic dosing in v1.
   - No closed-loop chemical control in v1.

## Non-goals for v1

- Automatic chlorine or acid dosing.
- Closed-loop control from probes/ORP.
- Scraping proprietary services.
- Depending on a hosted pool app.
- Requiring Home Assistant.
- Requiring nodejs-poolController.
- Building a custom Home Assistant integration before the standalone app works.
- Building a real nodejs-poolController plugin before the standalone app works.

## Cross-cutting requirements (from design review)

These surfaced while writing the UI/design plan. They touch both backend and
frontend, so they live here rather than in either companion plan:

1. **Both metric and US units, user-selectable.** Support gallons/lbs/°F *and*
   L/kg/°C — the user picks; the app is not US-only. A global unit setting flows
   through inputs, results, charts, and exports. Store canonical units in the DB
   and convert at the edges (recommend: normalize to SI internally, or
   store-as-entered + a unit field). The unit preference is app-wide for now and
   becomes a per-user preference once users exist (see #2).
2. **Single-user, no auth for now — but built so users can be added later.**
   v1 ships with no login and no `users` table; the deployment is trusted-LAN,
   single operator. Design choices must not block a future multi-user model:
   - **Pools are already multi-capable** — keep `pool_id` on every row and ship
     the pool switcher (renders as a plain title with one pool). Don't hardcode a
     single pool.
   - **Reserve the attribution seam** — plan for a future nullable `logged_by`
     (user id) on readings/additions, but do **not** build it yet. Leaving the
     column out now is fine; just don't design anything that would make adding it
     a painful migration.
   - **Future model (not now):** a `users` table + a `pool_members`
     (user_id, pool_id, role) join table is the intended growth path —
     household-shared or owner/editor/viewer sharing. Decide that when the need
     is real; v1 stays single-user.
   - The existing optional LAN password (see Security model) remains the only
     access control in v1.
3. **Timezones — local time, configurable.** `tested_at`/`added_at` are stored
   UTC but entered and displayed in local time. The timezone is a configurable
   app/pool setting (don't just assume the container's `TZ`); default to a sane
   local zone and let the user override it.
4. **Offline-capable PWA.** The pool is often the worst-Wi-Fi spot on the
   property. Ship installable + offline-read early; offline-write queue in
   Phase 4–5. SQLite stays canonical; the queue is just transport.
5. **Accessibility (WCAG AA) is a baseline, not a Phase 5 task.** Color is never
   the only signal; charts have table fallbacks; targets ≥ 48px; keyboard +
   screen-reader sane. Bake into component contracts.
6. **Jug/bag-aware dosing.** Store configurable jug and bag sizes so doses can
   read as "≈1.5 jugs" / "≈1 bag", not just raw oz/lbs.
7. **Volume helper.** Most owners don't know their exact volume — offer a
   shape+dimensions → volume helper in settings.

## Product shape

`openpool` should run as one Docker container with one mounted data directory:

```yaml
services:
  openpool:
    image: ghcr.io/OWNER/openpool:latest
    container_name: openpool
    ports:
      - "5280:5280"
    volumes:
      - ./data:/data
    environment:
      - OPENPOOL_DB=/data/openpool.sqlite
      - TZ=UTC
    restart: unless-stopped
```

Recommended stack:

```text
Python 3.13+
FastAPI
Uvicorn
SQLite
SQLModel or SQLAlchemy
Pydantic
Jinja2 templates
HTMX or Alpine.js
Chart.js
pytest
ruff
uv
Docker
```

Start server-rendered. A single-user pool logbook does not need a front-end framework parliament.

## Core pages

### Dashboard `/`

Shows:

- Latest readings.
- Current target mode: maintenance, SLAM/shock, spa, etc.
- Free chlorine target vs current.
- CSI / scale-corrosion warning.
- Last test age.
- Recommended actions.
- Recent additions.
- Optional equipment status from nodejs-poolController.

### New reading `/readings/new`

Fast manual entry:

- FC
- CC
- pH
- TA
- CH
- CYA
- salt
- borates
- water temperature
- filter pressure
- notes

After save:

- calculate derived values.
- update target status.
- show recommended chemical actions.
- offer quick chemical-addition logging.

### Calculator `/calculator`

Pool calculator page:

- current readings
- target readings
- pool volume
- chemical type/strength
- calculated dose
- expected side effects
- warnings when chemistry is approximate

### History `/history`

History ledger (tables):

- reading table
- chemical addition table
- maintenance table
- date filters
- CSV/JSON export controls
- mobile: rows collapse to stacked cards (see ui-design-plan §5.4)

### Trends `/trends`

Charting (split from history for clarity):

- charts for FC, CC, pH, TA, CH, CYA, salt, CSI, water temperature
- target band shaded behind each line
- chemical-addition markers on the timeline for cause/effect
- accessible text/table fallback for every chart

### Settings `/settings`

Pool/app settings:

- pool volume
- spa volume
- surface type
- sanitizer type
- target profiles
- default chlorine strength
- default acid strength
- default stabilizer type
- export settings
- optional read-only share token

### Share page `/share/{pool_id}`

Read-only human page with current pool status.

### Share JSON `/share/{pool_id}.json`

Read-only JSON endpoint for apps, dashboards, and automations.

Example shape:

```json
{
  "app": "openpool",
  "version": "0.1.0",
  "pool": {
    "id": "home",
    "name": "Home",
    "volumeGallons": 20000,
    "surface": "plaster",
    "sanitizer": "swg"
  },
  "overview": {
    "fc": 5.0,
    "cc": 0.0,
    "ph": 7.6,
    "ta": 80,
    "ch": 350,
    "cya": 70,
    "salt": 3200,
    "waterTemp": 82,
    "csi": 0.0,
    "testedAt": "2026-01-01T12:00:00Z"
  },
  "targets": {
    "mode": "maintenance",
    "fc": 5.0,
    "cya": 70
  },
  "recommendations": []
}
```

## API endpoints

Minimum v1 API:

```text
GET  /api/health
GET  /api/pools
POST /api/pools
GET  /api/pools/{pool_id}
PUT  /api/pools/{pool_id}

GET  /api/pools/{pool_id}/readings
POST /api/pools/{pool_id}/readings
GET  /api/pools/{pool_id}/readings/latest

GET  /api/pools/{pool_id}/additions
POST /api/pools/{pool_id}/additions

GET  /api/pools/{pool_id}/maintenance
POST /api/pools/{pool_id}/maintenance

POST /api/pools/{pool_id}/calculate
GET  /api/pools/{pool_id}/share.json
GET  /api/pools/{pool_id}/export/readings.csv
GET  /api/pools/{pool_id}/export/additions.csv
GET  /api/pools/{pool_id}/export/all.json
```

Optional later:

```text
GET  /api/home-assistant/discovery
POST /api/mqtt/publish
GET  /api/nodejs-poolcontroller/state
```

## Database model

SQLite should store primary facts, not just derived calculator output.

Suggested tables:

```sql
pool_profiles (
  id text primary key,
  name text not null,
  volume_gallons real not null,
  spa_volume_gallons real,
  surface text,
  sanitizer text,
  notes text,
  created_at text not null,
  updated_at text not null
)

pool_settings_history (
  id text primary key,
  pool_id text not null,
  changed_at text not null,
  key text not null,
  old_value text,
  new_value text,
  notes text
)

test_readings (
  id text primary key,
  pool_id text not null,
  tested_at text not null,
  fc real,
  cc real,
  tc real,
  ph real,
  ta real,
  ch real,
  cya real,
  salt real,
  borates real,
  water_temp_f real,
  filter_pressure real,
  csi real,
  source text not null default 'manual',
  notes text,
  created_at text not null
)

chemical_additions (
  id text primary key,
  pool_id text not null,
  added_at text not null,
  chemical text not null,
  strength_percent real,
  amount real not null,
  unit text not null,
  reason text,
  linked_reading_id text,
  notes text,
  created_at text not null
)

maintenance_events (
  id text primary key,
  pool_id text not null,
  event_at text not null,
  event_type text not null,
  notes text,
  created_at text not null
)

target_profiles (
  id text primary key,
  pool_id text not null,
  name text not null,
  mode text not null,
  config_json text not null,
  created_at text not null,
  updated_at text not null
)
```

## Chemistry math plan

Implement the math inside the project. External libraries can be used for comparison tests, but the project should own its calculation engine.

### v1 formulas

High-confidence calculations:

- Pool/spa volume conversions.
- Free chlorine dose from liquid chlorine.
- CYA/stabilizer dose.
- Salt dose.
- Calcium hardness dose.
- Total chlorine calculation.
- FC/CYA maintenance target lookup.
- SLAM/shock target lookup.

### v2 formulas

Medium-complexity chemistry:

- CSI.
- Optional LSI.
- pH lowering with muriatic acid.
- pH raising with soda ash/borax guidance.
- TA raising with baking soda.
- TA lowering as process guidance rather than a fake one-shot miracle.
- Chemical side effects:
  - trichlor affects FC, CYA, pH
  - dichlor affects FC, CYA
  - cal-hypo affects FC, CH
  - acid affects pH and TA

pH/TA recommendations should include confidence/warning text because carbonate chemistry is approximate in consumer calculators.

### v3 formulas

Later:

- Borates.
- SWG percent/runtime estimation.
- Overnight chlorine loss test helper.
- Shock/SLAM progress tracker.
- Evaporation/refill/dilution model.
- Trichlor puck planner.
- Chemical cost tracking.

## Validation strategy

Every formula needs tests.

Validation sources:

- Public pool-care articles and charts.
- Known chemistry identities.
- Manual comparisons against public calculators.
- Independent open-source chemistry libraries where available.
- Real-world sanity checks from user-entered logs.

Acceptance thresholds:

- Simple ppm/mass/volume dosing: within 1-2% of expected values.
- CSI/pH/TA: practical agreement with clearly marked assumptions.
- No recommendation should hide unit assumptions.

Test layout:

```text
tests/
  test_chlorine.py
  test_cya.py
  test_salt.py
  test_calcium.py
  test_targets.py
  test_csi.py
  fixtures/
    example_pool.json
    public_reference_examples.json
```

## Home Assistant export

Support two paths.

### REST sensors

Home Assistant can poll:

```text
http://openpool:5280/api/pools/example/share.json
```

Expose fields:

- FC
- CC
- pH
- TA
- CH
- CYA
- salt
- water temperature
- CSI
- target FC
- below target boolean
- last test time

### MQTT discovery

Optional later:

```text
openpool/example/fc
openpool/example/cc
openpool/example/ph
openpool/example/ta
openpool/example/ch
openpool/example/cya
openpool/example/salt
openpool/example/csi
openpool/example/target_fc
openpool/example/below_target
```

## nodejs-poolController integration

Do not couple v1 to nodejs-poolController internals.

Support three simple paths:

1. **Read-only equipment state pull**
   - Configure a nodejs-poolController state URL.
   - Display pool temperature, pump, and circuit state in openpool.

2. **JSON endpoint for external dashboards**
   - Dashboards can read `/api/pools/{pool_id}/share.json`.

3. **Iframe/link integration**
   - Link or embed openpool wherever convenient.

A true plugin can come later only if the dashboard extension model is clean.

## Import/export

### CSV export

Required:

- readings CSV
- chemical additions CSV
- maintenance CSV

### JSON export

Required:

- latest reading JSON
- all-data backup JSON
- share JSON

### CSV import

Required before v1.0:

- readings CSV import
- additions CSV import

### Hosted-app import

Optional:

- one-time import from a public share JSON if a user provides one.
- treat it as latest/profile seed unless the remote endpoint proves it exposes full history.

## Security model

Default assumption: LAN-only app.

Minimum security posture:

- Bind to LAN/private network by default.
- No write endpoints exposed publicly without auth.
- Optional single-user password.
- Optional read-only share token.
- Share endpoint must never expose private notes unless explicitly enabled.
- Docker container runs as non-root.
- SQLite data lives in a mounted volume.
- Backups/export should not include secrets.

Share token examples:

```text
/share/example?token=<read-token>
/share/example.json?token=<read-token>
```

## Repository layout

```text
openpool/
  app/
    __init__.py
    main.py
    config.py
    db.py
    models.py
    schemas.py
    chemistry/
      __init__.py
      chlorine.py
      cya.py
      salt.py
      calcium.py
      csi.py
      targets.py
      dosing.py
    routers/
      pages.py
      api.py
      export.py
      importers.py
      integrations.py
    templates/
      base.html
      dashboard.html
      reading_form.html
      calculator.html
      history.html
      trends.html
      settings.html
      share.html
    static/
      tokens.css          # design tokens: color/type/space/themes
      app.css
      app.js
      manifest.webmanifest # PWA
      sw.js                # service worker
  plans/
    openpool-plan.md
    math-plan.md
    ui-design-plan.md
  tests/
  docs/
    formulas.md
    ui-components.md       # component contracts for collaborators
    api.md
    deployment.md
  Dockerfile
  docker-compose.yml
  pyproject.toml
  README.md
```

## Build phases

### Phase 0 — skeleton

Deliverables:

- FastAPI skeleton.
- SQLite initialization.
- Docker compose.
- `/api/health`.
- Basic dashboard page.

Verification:

- `docker compose up` works.
- `/api/health` returns OK.

### Phase 1 — settings and logbook

Deliverables:

- Pool profile/settings page.
- New reading form.
- Reading history table.
- SQLite persistence.
- CSV export.

Verification:

- Enter sample readings.
- Refresh browser; values persist.
- CSV export contains the row.

### Phase 2 — math MVP

Deliverables:

- Liquid chlorine dose.
- CYA/stabilizer dose.
- Salt dose.
- Maintenance and shock/SLAM target lookup.
- Calculator page.
- Golden tests.

Verification:

- Formula tests pass.
- Calculator output matches public reference examples within tolerance.

### Phase 3 — dashboard

Deliverables:

- Latest readings cards.
- Target status card.
- CSI/status card.
- Charts.
- Last-test age.
- Recommended actions.

Verification:

- Phone-friendly dashboard works locally.
- Latest reading and recommendation visible in one glance.

### Phase 4 — integrations

Deliverables:

- `/share/{pool_id}` HTML page.
- `/share/{pool_id}.json` endpoint.
- Home Assistant REST example.
- Optional MQTT export.
- Optional nodejs-poolController state display.

Verification:

- External client can read share JSON.
- Home Assistant can poll the endpoint.

### Phase 5 — hardening

Deliverables:

- Optional auth/read-token.
- CSV import.
- JSON backup/restore.
- Better validation/error handling.
- Docs.
- CI.

Verification:

- Backup/restore tested.
- Formula tests pass in CI.

## Public repository / idea protection note

This public plan intentionally avoids personal pool data, network details, private deployment details, and exact proprietary implementation material.

A public repository cannot prevent people from copying an idea. The protection strategy is:

- publish a clear product direction without private data.
- withhold any proprietary/private deployment details.
- do not publish secrets, tokens, IPs, personal names, or real pool history.
- do not add an open-source license until the owner chooses the license.
- keep implementation quality, validation fixtures, and operational polish as the real moat.

If an open-source license is added later, choose it deliberately.

## First implementation task

Create `openpool`, a FastAPI + SQLite + Docker local pool chemistry logbook. Implement pool profile storage, manual reading entry, reading history table, CSV export, `/api/pools/example/share.json`, and initial chlorine/CYA/salt dose calculations with tests. Keep UI server-rendered and mobile-friendly. No Home Assistant writes, no nodejs-poolController writes, no automatic dosing.
