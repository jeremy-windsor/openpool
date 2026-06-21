# Deployment

`openpool` is designed for LAN-first Docker deployment.

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
ghcr.io/jeremy-windsor/openpool:<short-git-sha>
ghcr.io/jeremy-windsor/openpool:<version>
```

Use the published-image compose file:

```bash
docker compose -f docker-compose.ghcr.yml pull
docker compose -f docker-compose.ghcr.yml up -d
docker compose -f docker-compose.ghcr.yml logs -f openpool
```

Health check:

```bash
curl http://127.0.0.1:5280/api/health
curl http://127.0.0.1:5280/api/version
```

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

Acceptable early exposure is localhost, SSH tunnel, private VPN, or a trusted
LAN/VLAN where every client is allowed to read and write pool data. Anything
else needs auth first. No exceptions; future-you is tired of cleaning up
avoidable nonsense.

## Pilot Checklist

Run this list before and during a few weeks of real-pool use.

Before the pilot:

- [ ] Pull the latest image and confirm `/api/version` matches the expected
      commit.
- [ ] Set pool volume, sanitizer type, timezone, and chlorine strength in
      Settings.
- [ ] Confirm the SQLite `/data` volume or Postgres named volume is on storage
      that survives container recreation.
- [ ] Take a `all.json` backup and confirm it downloads and parses.
- [ ] Confirm the app is reachable only via localhost, VPN, or trusted LAN.

During the pilot, daily or per-test:

- [ ] Log readings from the test kit; confirm CSI appears when pH/TA/CH are
      present.
- [ ] Use the calculator for every dose and log it with "Log this dose".
- [ ] Log maintenance events (backwash, cleaning, refills) as they happen.

Weekly:

- [ ] Download `all.json` as a backup.
- [ ] Skim history for entry mistakes; fix them with Edit instead of
      re-entering.
- [ ] Note anything annoying or missing in `plans/project-tracker.md` under
      Active Concerns.

Known not-yet-built (do not rediscover): charts/trends, metric units in the
UI, import/restore, authentication, multi-user. See the tracker.
