# Deployment

`openpool` is designed for LAN-first Docker deployment.

```bash
docker compose up --build
```

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

If the GHCR package is private, log in on the Docker host first:

```bash
echo "<github-token>" | docker login ghcr.io -u jeremy-windsor --password-stdin
```

The compose file binds to localhost by default:

```text
127.0.0.1:5280:5280
```

That is deliberate until authentication exists. Put a reverse proxy or VPN in
front of it before exposing it beyond the host. The container stores SQLite data
at:

Set the pool's default timezone for new deployments:

```yaml
environment:
  OPENPOOL_TIMEZONE: America/Phoenix
  TZ: America/Phoenix
```

```text
./data/openpool.sqlite
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
- [ ] Confirm the `/data` volume is on storage that survives container
      recreation.
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
