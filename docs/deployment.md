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

Acceptable early exposure is localhost, SSH tunnel, private VPN, or a trusted
LAN/VLAN where every client is allowed to read and write pool data. Anything
else needs auth first. No exceptions; future-you is tired of cleaning up
avoidable nonsense.
