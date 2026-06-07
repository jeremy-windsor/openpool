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

## Readings

```text
GET  /api/pools/{pool_id}/readings
POST /api/pools/{pool_id}/readings
GET  /api/pools/{pool_id}/readings/latest
```

## Additions

```text
GET  /api/pools/{pool_id}/additions
POST /api/pools/{pool_id}/additions
```

## Calculator

```text
POST /api/pools/{pool_id}/calculate
```

Supported goals:

- `raise_fc`
- `raise_cya`
- `raise_salt`

## Exports and Share

```text
GET /api/pools/{pool_id}/export/readings.csv
GET /api/pools/{pool_id}/export/additions.csv
GET /api/pools/{pool_id}/export/all.json
GET /api/pools/{pool_id}/share.json
GET /share/{pool_id}
GET /share/{pool_id}.json
```

Share endpoints are disabled until `share_enabled` is true and a read token is
configured. Share JSON excludes private notes unless `include_notes_in_share` is
enabled on the pool profile. Pool API responses do not echo share tokens.
