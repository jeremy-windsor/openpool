# API

The API is intentionally small. Write endpoints are for trusted LAN deployment
until authentication is added.

## Health

```text
GET /api/health
GET /api/version
```

Returns:

```json
{"ok": true, "app": "openpool"}
```

## Pools

```text
GET  /api/pools
POST /api/pools
GET  /api/pools/{pool_id}
PUT  /api/pools/{pool_id}
```

Pool IDs are limited to letters, numbers, underscores, and dashes.
`surface` is one of `plaster`, `fiberglass`, or `vinyl`; plaster includes
cementitious pebble and aggregate finishes for calculation grouping.
`sanitizer` is `liquid_chlorine` or `swg`; the legacy
`salt_water_generator` spelling is accepted for existing clients. Creating an
already-existing pool ID returns `409`.

## Readings

```text
GET    /api/pools/{pool_id}/readings
POST   /api/pools/{pool_id}/readings
GET    /api/pools/{pool_id}/readings/latest
GET    /api/pools/{pool_id}/readings/{reading_id}
PUT    /api/pools/{pool_id}/readings/{reading_id}
DELETE /api/pools/{pool_id}/readings/{reading_id}
```

`PUT` is a partial update: only the fields sent are changed. `tc` and `csi` are
server-owned derived fields; clients that send either receive `422`. The server
always recomputes them on create and edit. Each reading also carries
`csi_meta_json`/`csi_meta`, which records formula version, inputs, defaults, and
warnings so an approximate CSI is not presented as a lab measurement (see
`docs/formulas.md`).

Reading, pool, and addition numbers have hard physical bounds. Values outside
those bounds receive `422` at the API boundary. A linked addition must reference
a reading from the same pool.

## Additions

```text
GET    /api/pools/{pool_id}/additions
POST   /api/pools/{pool_id}/additions
PUT    /api/pools/{pool_id}/additions/{addition_id}
DELETE /api/pools/{pool_id}/additions/{addition_id}
```

## Maintenance

```text
GET    /api/pools/{pool_id}/maintenance
POST   /api/pools/{pool_id}/maintenance
PUT    /api/pools/{pool_id}/maintenance/{event_id}
DELETE /api/pools/{pool_id}/maintenance/{event_id}
```

`event_type` is required (for example `backwash`, `clean_filter`, `vacuum`).
`event_at` defaults to now and is stored as UTC.

## Calculator

```text
POST /api/pools/{pool_id}/calculate
```

Supported goals:

- `raise_fc` - optional `product`: `liquid_chlorine` (default), `trichlor`,
  `dichlor`, or `cal_hypo`. Dry products return expected side effects
  (`effects`) such as CYA or CH rise.
- `slam_fc` - needs `current` (FC); optional `cya` sets the shock target from
  the FC/CYA chart. `target` is ignored.
- `raise_cya`
- `raise_salt`
- `raise_ch`
- `raise_ta`
- `lower_ph` - needs `current`/`target` (pH) and `ta`; optional `cya` and
  `borates`. Returns muriatic acid fl oz plus the expected TA drop. Approximate.
- `raise_ph` - same inputs as `lower_ph`; returns soda ash oz weight plus the
  expected TA rise. Approximate; aeration is suggested first.
- `lower_by_dilution` - `current`/`target` of any dilution-only reading (CYA,
  salt, CH, borates). Returns gallons of water to replace.
- `swg_runtime` - needs `target` (FC ppm per day) and `cell_lbs_per_day`;
  optional `pump_hours` (default 24). Returns the percent output setting.

Request fields: `goal`, `current`, `target`, `pool_gallons`, `strength`,
`product`, `ta`, `cya`, `borates`, `cell_lbs_per_day`, `pump_hours`. Missing
required inputs for a goal return `400` with the missing names.

## Exports and Share

```text
GET /api/pools/{pool_id}/export/readings.csv
GET /api/pools/{pool_id}/export/additions.csv
GET /api/pools/{pool_id}/export/maintenance.csv
GET /api/pools/{pool_id}/export/all.json
GET /api/pools/{pool_id}/share.json
GET /share/{pool_id}
GET /share/{pool_id}.json
```

`all.json` is a portable inspection/interchange export. It is not a native
database backup and cannot currently be restored through OpenPool.
Export routes return the complete stored history rather than the normal
100-record list view.

The readings CSV and portable JSON include stored CSI provenance.

Share endpoints are disabled until `share_enabled` is true and a read token is
configured. Share JSON excludes private notes unless `include_notes_in_share` is
enabled on the pool profile. Pool API responses do not echo share tokens.
