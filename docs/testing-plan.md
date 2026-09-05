# Testing Plan

OpenPool supports SQLite by default and optional PostgreSQL. The committed suite
tests shared behavior, backend-specific persistence, chemistry safety policy,
exports, backup handling, and deployment guardrails.

## Automated Coverage

| Area | Evidence |
|------|----------|
| Chemistry formulas and safety boundaries | `tests/test_chemistry.py`, `tests/test_services.py`, public fixtures under `tests/fixtures/` |
| FastAPI routes, forms, share views, and exports | `tests/test_api.py` |
| SQLite CRUD, migrations, constraints, timestamps, and schema preflight | `tests/test_persistence.py` |
| Native SQLite backup integrity and no-clobber behavior | `tests/test_backup.py` |
| PostgreSQL CRUD parity and SQLite-to-PostgreSQL copy | `tests/test_postgres.py` |
| Compose loopback binding and Docker build-context allowlist | `tests/test_deployment.py` |

The persistence suite includes adversarial cases for future-version databases,
forged current-version schemas, migration rollback after DDL, corrupt CSI
metadata, duplicate pool creation, explicit zero values, and unbounded export
queries. API tests reject blank required strings, booleans used as physical
numbers, unsupported sanitizer values, malformed form encoding, and
cross-origin writes.

## Backend Matrix

### SQLite

SQLite tests run without `OPENPOOL_DATABASE_URL`. They cover application startup,
schema upgrades, database constraints, the full route layer, and native backup.
Schema creation and upgrades run in one explicit transaction. A database with a
newer schema version is rejected before OpenPool creates or changes application
tables.

### PostgreSQL

`tests/test_postgres.py` needs `OPENPOOL_TEST_DATABASE_URL`. The tests compare
SQLite and PostgreSQL CRUD snapshots and run the real migration command. If the
variable is set and PostgreSQL is unavailable or broken, the tests fail; they do
not silently skip. GitHub Actions supplies a PostgreSQL service, so both parity
tests execute in CI.

### SQLite-to-PostgreSQL migration

`openpool-migrate`:

- requires the source SQLite database to be at the current schema version;
- validates every copied source column before writing;
- holds one SQLite read transaction across validation, counts, and copied rows;
- writes the destination in a transaction; and
- rolls back the destination copy on failure.

The PostgreSQL integration test covers the full copy. The local dry-run test
covers source validation and row-count reporting without a PostgreSQL server.

## Run Locally

SQLite and all non-PostgreSQL checks:

```bash
uv run ruff check .
uv run pytest -q
node --test tests/calculator.test.cjs
git diff --check
```

The two PostgreSQL tests skip only when `OPENPOOL_TEST_DATABASE_URL` is unset.
The Node tests exercise calculator product/goal transitions and confirmation
invalidation without browser dependencies. `tests/test_strength_safety.py`
checks the same safety boundary through the service, HTML, and JSON API.

To run them locally, start a disposable PostgreSQL instance and point the suite
at it:

```bash
docker run -d --name openpool-test-pg \
  -e POSTGRES_USER=openpool \
  -e POSTGRES_PASSWORD=change-me \
  -e POSTGRES_DB=openpool_test \
  -p 15432:5432 \
  postgres:16-alpine

OPENPOOL_TEST_DATABASE_URL=postgresql://openpool:change-me@localhost:15432/openpool_test \
  uv run pytest -q
```

Use a disposable database. The PostgreSQL tests create and delete test records.

## CI

`.github/workflows/docker.yml` currently:

1. starts PostgreSQL 16 and waits for `pg_isready`;
2. installs locked development and PostgreSQL dependencies;
3. runs Ruff and the full pytest suite with PostgreSQL enabled; and
4. allows image publication only after the test job passes.

## Manual Release Checks

Automated tests do not replace these deployment checks:

- Build the image and verify `/api/health` and `/api/version`.
- Confirm the published port remains bound to `127.0.0.1`.
- Restart the container and verify SQLite or PostgreSQL data persists.
- Restore a native SQLite backup into scratch storage and verify row counts.
- If using an HTTPS reverse proxy, verify one legitimate write and one rejected
  mismatched-Origin write with the exact proxy trust configuration.
- Verify an immutable image tag before recommendation-following pilot use.
