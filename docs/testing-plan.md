# Testing Plan

Validation strategy for OpenPool's dual-backend support (SQLite + PostgreSQL).

## Test categories

### 1. SQLite default path (existing behavior)

**Goal**: confirm nothing changed when no `OPENPOOL_DATABASE_URL` is set.

| Check | How | Automated? |
|-------|-----|------------|
| App starts and serves requests | `docker compose up`, curl `/api/health` | CI |
| Create pool, reading, addition, maintenance via API | `tests/test_api.py`, `tests/test_persistence.py` | Yes (83 tests) |
| Chemistry calculations unchanged | `tests/test_chemistry.py` | Yes |
| CSV/JSON export unchanged | `tests/test_api.py` | Yes |
| Share endpoints unchanged | `tests/test_persistence.py` | Yes |
| SQLite file created at expected path | Manual: check `/data/openpool.sqlite` exists | Manual |
| Data survives container restart | Manual: restart container, verify readings still present | Manual |

### 2. PostgreSQL backend (new path)

**Goal**: confirm CRUD operations produce identical results to SQLite.

| Check | How | Automated? |
|-------|-----|------------|
| Schema creates all tables with correct types | `tests/test_postgres.py::test_postgres_crud_matches_sqlite` | Yes (needs PG) |
| CRUD parity: same pool, reading, addition, maintenance operations produce same results on both backends | `tests/test_postgres.py::test_postgres_crud_matches_sqlite` | Yes (needs PG) |
| `real` columns stored as `double precision` (8-byte, not 4-byte) | Covered by parity test (float round-trip) | Yes |
| TEXT timestamps (not `timestamptz`) | Covered by parity test (string comparison) | Yes |
| INTEGER booleans (not `boolean`) | Covered by parity test | Yes |
| FK cascade deletes work | Covered by parity test (pool delete cascades) | Yes |
| Connection failure handled gracefully | Manual: set bad URL, verify app reports error | Manual |
| Missing psycopg gives clear error | `tests/test_persistence.py::test_connect_rejects_libpq_keyword_dsn` | Yes |

### 3. Migration tool (`openpool-migrate`)

**Goal**: SQLite data arrives in PostgreSQL intact.

| Check | How | Automated? |
|-------|-----|------------|
| Dry-run reports row counts without writing | `tests/test_postgres.py::test_migration_copies_sqlite_rows_to_postgres` | Yes (needs PG) |
| Full migration copies all tables in FK order | Same test verifies row counts match | Yes (needs PG) |
| Idempotency: running twice does not duplicate or fail (ON CONFLICT DO NOTHING) | Run migration twice, verify counts unchanged | Manual |
| `--truncate` clears destination before copying | Manual: run with `--truncate`, verify target has only source rows | Manual |
| Migration aborts cleanly on connection failure | Manual: point at unreachable PG, verify no partial data | Manual |
| Transaction safety: bulk load is atomic | Covered by migration using `autocommit=False` with `commit()/rollback()` | Yes (code path) |

### 4. Cross-backend behavioral parity

**Goal**: same data in SQLite and PostgreSQL produces identical API responses.

| Check | How |
|-------|-----|
| Seed both backends with identical data, compare `/api/pools/{id}` responses | Manual or script |
| Compare `/api/pools/{id}/readings` ordering and values | Manual or script |
| Compare `/api/pools/{id}/share.json` output | Manual or script |
| Compare CSV export byte-for-byte | Manual or script |
| Chemistry calculations (CSI, dosing, targets) produce same results | Covered by `test_postgres_crud_matches_sqlite` |

### 5. Docker Compose validation

| Mode | Check | How |
|------|-------|-----|
| SQLite (`docker-compose.yml`) | App starts, health check passes, data persists after restart | Manual |
| PostgreSQL (`docker-compose.postgres.yml`) | Both `db` and `openpool` start, health checks pass | Manual |
| PostgreSQL | `openpool` waits for `db` healthy before starting (depends_on) | Manual |
| PostgreSQL | Data persists in named volume after `docker compose down` + `up` | Manual |
| PostgreSQL | App not exposed publicly (bound to `127.0.0.1`) | Manual: check port binding |

### 6. Edge cases

| Scenario | Expected behavior | Test |
|----------|-------------------|------|
| `OPENPOOL_DATABASE_URL` not set | SQLite mode, no psycopg import | Existing tests |
| `OPENPOOL_DATABASE_URL` set to valid PG URL | PostgreSQL mode | `test_postgres.py` |
| `OPENPOOL_DATABASE_URL` set to libpq keyword DSN (`host=... dbname=...`) | ValueError, clear message | `test_persistence.py::test_connect_rejects_libpq_keyword_dsn` |
| `OPENPOOL_DATABASE_URL` set to garbage | ValueError, clear message | `test_persistence.py::test_database_url_rejects_malformed_value` |
| psycopg not installed but PG URL set | RuntimeError: "install with the postgres extra" | Manual |
| Postgres server down/unreachable | Connection error at request time | Manual |
| Migration source SQLite file missing | Error before any writes | Manual |
| Migration target already has data | ON CONFLICT DO NOTHING skips existing rows | Manual |

## Running tests

### SQLite only (default, no dependencies)

```bash
uv run pytest -q
```

All 85 tests run. Two Postgres tests skip automatically.

### With PostgreSQL parity tests

Start a Postgres instance:

```bash
docker run -d --name openpool-test-pg \
  -e POSTGRES_USER=openpool \
  -e POSTGRES_PASSWORD=*** \
  -e POSTGRES_DB=openpool_test \
  -p 15432:5432 \
  postgres:16-alpine
```

Run the full suite with the test database URL:

```bash
OPENPOOL_TEST_DATABASE_URL=postgresql://openpool:***@localhost:15432/openpool_test \
  uv run pytest -q
```

All 87 tests run (85 SQLite + 2 Postgres parity).

### Lint

```bash
uv run ruff check .
```

## CI considerations

The existing GitHub Actions workflow (`.github/workflows/`) runs the SQLite test suite automatically. To add Postgres coverage in CI:

1. Add a `services:` block to the test job with `postgres:16-alpine`.
2. Set `OPENPOOL_TEST_DATABASE_URL` to point at the service container.
3. Run the full suite — Postgres tests will execute instead of skipping.

Example CI service block:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    env:
      POSTGRES_USER: openpool
      POSTGRES_PASSWORD: openpool
      POSTGRES_DB: openpool_test
    ports:
      - 5432:5432
    options: >-
      --health-cmd "pg_isready -U openpool"
      --health-interval 5s
      --health-timeout 5s
      --health-retries 12
```

## Test matrix

| Test file | SQLite | PostgreSQL | Notes |
|-----------|--------|------------|-------|
| `tests/test_chemistry.py` | ✅ | N/A | Pure math, no DB |
| `tests/test_api.py` | ✅ | N/A | API layer over SQLite fixture |
| `tests/test_persistence.py` | ✅ | N/A | SQLite-specific (temp files, pragmas) |
| `tests/test_postgres.py` | ⏭️ skip | ✅ | Requires `OPENPOOL_TEST_DATABASE_URL` |

## What belongs in this repo

The following are appropriate for a public repository:

- Source code (`openpool/`)
- Tests (`tests/`)
- Documentation (`docs/`, `README.md`)
- Docker configuration (`Dockerfile`, `docker-compose*.yml`)
- CI workflows (`.github/workflows/`)
- Plans (`plans/`)

Example credentials in compose files and docs (e.g., `openpool:***@db:5432`) are standard practice. Document that users must change default passwords before any non-local exposure.
