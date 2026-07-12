# Deployment

`openpool` is designed for local-first Docker deployment.

> **Current release posture:** Gate P is implemented and verified for a
> supervised, single-owner pilot. Recommendation-following access is limited
> to an immutable reviewed image over loopback, an SSH tunnel, or a private
> VPN. Public/LAN-wide write access remains blocked until authentication exists.

```bash
docker compose up --build
```

SQLite is the default backend. With no database environment changes, the app
stores data at `OPENPOOL_DB`, which defaults to `data/openpool.sqlite` for local
development and `/data/openpool.sqlite` in the container.

For local Python development:

```bash
uv sync --extra dev
uv run uvicorn openpool.main:app --reload --host 127.0.0.1 --port 5280
```

## Published Image

Images are published to GitHub Container Registry from GitHub Actions:

```text
ghcr.io/jeremy-windsor/openpool:latest
ghcr.io/jeremy-windsor/openpool:sha-<short-git-sha>
ghcr.io/jeremy-windsor/openpool:<version>
```

Use the published-image compose file:

```bash
docker compose -f docker-compose.ghcr.yml pull
docker compose -f docker-compose.ghcr.yml up -d
docker compose -f docker-compose.ghcr.yml logs -f openpool
```

`latest` is for development only. A recommendation-following pilot must pin
the reviewed commit instead of accepting unattended updates:

```bash
OPENPOOL_IMAGE=ghcr.io/jeremy-windsor/openpool:sha-<short-git-sha> \
  docker compose -f docker-compose.ghcr.yml up -d
```

Health check:

```bash
curl http://127.0.0.1:5280/api/health
curl http://127.0.0.1:5280/api/version
```

## SQLite Backup And Restore Drill

Create a WAL-safe, integrity-checked native backup while OpenPool is running:

```bash
docker exec openpool openpool-backup \
  --source /data/openpool.sqlite \
  --output /data/backups/openpool-$(date -u +%Y%m%dT%H%M%SZ).sqlite
```

The command refuses to overwrite an existing backup. Copy the resulting file
off the live service path. Operators with the SQLite CLI may use its equivalent
online-backup command:

```bash
sqlite3 /data/openpool.sqlite ".backup /safe/path/openpool.sqlite"
```

Restore drills use scratch storage; never overwrite the live database in place:

1. Stop a scratch OpenPool container, not the live service.
2. Copy the backup to a scratch `/data/openpool.sqlite` path.
3. Start the pinned OpenPool image against that scratch directory on a spare
   loopback port, using the same runtime UID/GID as production so the restored
   `0600` database is readable.
4. Verify `/api/health`, the dashboard, and row counts for pools, readings,
   additions, and maintenance.
5. Record the tested image revision, backup filename, integrity result, and row
   counts in the project tracker.

`all.json` remains a portable export for inspection/interchange. It is not the
disaster-recovery mechanism because OpenPool has no round-trip JSON restore.

## PostgreSQL Backend

PostgreSQL is optional. Set `OPENPOOL_DATABASE_URL` to use it:

```bash
OPENPOOL_DATABASE_URL=postgresql://openpool:openpool@localhost:5432/openpool \
  uv run uvicorn openpool.main:app --host 127.0.0.1 --port 5280
```

Install the optional driver for non-Docker Python runs:

```bash
uv sync --extra dev --extra postgres
```

The Docker image installs the Postgres extra, so the same image works in SQLite
and PostgreSQL modes. A local Postgres stack is available:

```bash
docker compose -f docker-compose.postgres.yml up --build
docker compose -f docker-compose.postgres.yml logs -f openpool
```

The stack uses `postgres:16-alpine`, a named `openpool-postgres` volume, and an
`openpool` service that waits for `pg_isready` before starting.

To migrate existing SQLite data into PostgreSQL:

```bash
OPENPOOL_DATABASE_URL=postgresql://openpool:openpool@localhost:5432/openpool \
  uv run openpool-migrate --sqlite data/openpool.sqlite --dry-run
OPENPOOL_DATABASE_URL=postgresql://openpool:openpool@localhost:5432/openpool \
  uv run openpool-migrate --sqlite data/openpool.sqlite
```

The migration copies `pool_profiles`, `test_readings`, `chemical_additions`,
and `maintenance_events` in foreign-key order with `ON CONFLICT DO NOTHING`.
Use `--truncate` to clear those destination tables in the same transaction
before copying.

PostgreSQL parity tests are skipped unless `OPENPOOL_TEST_DATABASE_URL` points
at a test database:

```bash
OPENPOOL_TEST_DATABASE_URL=postgresql://openpool:openpool@localhost:5432/openpool_test \
  uv run pytest tests/test_postgres.py -q
```

If the GHCR package is private, log in on the Docker host first:

```bash
echo "<github-token>" | docker login ghcr.io -u jeremy-windsor --password-stdin
```

The compose file binds to localhost by default:

```text
127.0.0.1:5280:5280
```

That is deliberate until authentication exists. Put a reverse proxy or VPN in
front of it before exposing it beyond the host.

Set the pool's default timezone for new deployments:

```yaml
environment:
  OPENPOOL_TIMEZONE: America/Phoenix
  TZ: America/Phoenix
```

Do not expose the service to the public internet yet. v1 has no login system.
Public exposure should wait for authentication, token handling, rate limits, and
reverse-proxy hardening.

If you put `openpool` behind a reverse proxy, preserve the original `Host`
header and pass standard forwarded headers such as `X-Forwarded-For`,
`X-Forwarded-Proto`, and `Forwarded`. The app's write-safety checks compare
request origin information to the effective host, so proxy header rewriting can
break legitimate form/API writes or weaken those checks.

Logging-only development use may run on a trusted LAN/VLAN only when every
client is allowed to read and write pool data and the operator accepts that
risk. Recommendation-following use requires loopback, an SSH tunnel, or a
private VPN until authentication exists. Public or semi-public exposure is
blocked until Gate X.

## Development And Pilot Checklist

Gate P implementation evidence is recorded in `plans/project-tracker.md`.
Each deployment still has to complete the operator checks below; passing the
software gate does not verify a pool volume, a chemical label, or a network.

For logging-only development:

- [ ] Pull the latest image and confirm `/api/version` matches the expected
      commit.
- [ ] Set pool volume, sanitizer type, timezone, and chlorine strength in
      Settings.
- [ ] Confirm the SQLite `/data` volume survives container recreation.
- [ ] Keep recommendations development-only; dose from an independent source.
- [ ] If LAN-bound, record that every reachable client can currently write.

Before recommendation-following pilot use:

- [x] Gate P is recorded complete in `plans/project-tracker.md`.
- [ ] Pin an immutable `sha-<short-git-sha>` image; disable unattended updates.
- [ ] Confirm `/api/version.buildSha` matches the pinned commit.
- [ ] Bind to `127.0.0.1` and use loopback, SSH tunnel, or private VPN access.
- [ ] Take a native SQLite backup, restore it to scratch storage, and verify the
      app can read the restored database. `all.json` is an export, not a backup.
- [ ] Recheck pool settings and establish a trusted latest reading after
      removing any prior LAN-wide write exposure.

During the pilot:

- [ ] Log every reading, dose actually applied, and maintenance event.
- [ ] Retest after dosing; never repeat a recommendation from an old reading.
- [ ] Repeat the native backup and restore drill on schedule.
- [ ] Skim history for entry mistakes; fix them with Edit instead of
      re-entering.
- [ ] Note anything annoying or missing in `plans/project-tracker.md` under
      Active Concerns.

Known not-yet-built (do not rediscover): charts/trends, metric units in the
UI, import/restore, authentication, multi-user. See the tracker.
