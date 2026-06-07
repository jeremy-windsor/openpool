# Review Notes

Date: 2026-06-07

Scope: first implementation slice after the planning phase.

## Built

- FastAPI app skeleton with server-rendered pages.
- SQLite profile, reading, chemical addition, and maintenance tables.
- Manual reading entry, history, additions entry, calculator, settings, and share page.
- API endpoints for health, pools, readings, additions, calculator, share JSON, CSV export, and JSON backup.
- Initial chemistry helpers for liquid chlorine, dry stabilizer/CYA, salt, and FC/CYA targets.
- Dockerfile and compose file.

## Security Review

Mitigations added during review:

- Compose binds to `127.0.0.1:5280:5280` by default.
- Container runs as a non-root user and drops Linux capabilities in compose.
- Cross-origin write requests are rejected by middleware.
- Pool API responses do not echo share tokens or private pool notes.
- Share endpoints are disabled by default and require an explicit token when enabled.
- Share token comparison uses constant-time comparison.
- SQLite uses parameterized SQL, constrained pool IDs, WAL, foreign keys, and a busy timeout.
- CSV exports escape spreadsheet formula-leading text values.
- Service worker no longer serves stale cached dashboard HTML while offline.
- Private reading notes are excluded from share JSON unless explicitly enabled.

Remaining risks:

- There is still no real authentication. This is trusted-host/LAN software only.
- API write endpoints remain open to clients that can reach the service.
- Share tokens are stored in SQLite as plaintext until auth/secrets handling exists.
- No rate limiting yet.

## Adversarial Review

Findings addressed:

- UI form writes now go through the same Pydantic validation as API writes.
- Naive `datetime-local` input is converted from the pool timezone to UTC.
- Calculator results expose formula, source note, assumptions, warnings, and confidence.
- Calculator accepts a volume override for spa/partial-volume calculations.
- Chemical additions can be logged from the browser UI.
- Additions CSV and all-data JSON export were added.
- Run docs now include both Docker and `uv` development paths.

Known gaps:

- A committed `tests/` suite (chemistry + persistence + FastAPI routes, 32
  tests) now runs in GitHub Actions and gates the container build. Route tests
  surfaced and fixed a SQLite cross-thread bug in async page routes.
- Metric support is not implemented beyond the stored preference.
- Maintenance event UI/API/export and settings-history logging are still future work.
- Authentication is the next hardening step before any non-local exposure.

