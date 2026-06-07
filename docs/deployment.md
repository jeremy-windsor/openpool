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

The compose file binds to localhost by default:

```text
127.0.0.1:5280:5280
```

That is deliberate until authentication exists. Put a reverse proxy or VPN in
front of it before exposing it beyond the host. The container stores SQLite data
at:

```text
./data/openpool.sqlite
```

Do not expose the service to the public internet yet. v1 has no login system.
Public exposure should wait for authentication, token handling, rate limits, and
reverse-proxy hardening.
