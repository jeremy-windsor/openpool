# openpool

Self-hosted pool chemistry logbook and calculator.

`openpool` is planned as a small Docker-hosted web app for pool owners who want local history, transparent calculations, and portable exports without depending on a hosted app just to publish their latest chemistry as JSON.

## Planned shape

- FastAPI backend
- SQLite local database
- Mobile-friendly web UI
- Pool chemistry calculator using public pool-care methodology and first-principles chemistry
- Test reading history
- Chemical addition history
- Maintenance history
- CSV export
- JSON export
- Shareable read-only JSON endpoint
- Optional Home Assistant export
- Optional nodejs-poolController integration

## Status

Early implementation. The repository now contains the first FastAPI + SQLite
slice: pool profile storage, manual reading entry, reading history, CSV export,
share JSON, and initial chlorine/CYA/salt calculations.

## Run locally

Docker:

```bash
docker compose up --build
```

Then open:

```text
http://localhost:5280
```

Python development environment:

```bash
uv sync --extra dev
uv run uvicorn openpool.main:app --reload --host 127.0.0.1 --port 5280
```

This repository does not vendor dependencies. A host needs either Docker or the
Python dependencies from `pyproject.toml` installed in an environment.

## Tests and linting

```bash
uv sync --extra dev
uv run ruff check .
uv run pytest -q
```

The committed suite under `tests/` covers the chemistry engine (with public
reference fixtures in `tests/fixtures/`), SQLite persistence, and FastAPI
routes. GitHub Actions runs ruff and pytest on every push and pull request, and
the container image only publishes after that job passes.

Published GHCR image, after the GitHub Actions build has run:

```bash
docker compose -f docker-compose.ghcr.yml pull
docker compose -f docker-compose.ghcr.yml up -d
```

The compose files bind to `127.0.0.1` by default. Keep it behind localhost,
SSH tunnel, VPN, or a trusted reverse proxy until authentication exists.

See:

- [`plans/openpool-plan.md`](plans/openpool-plan.md)
- [`plans/math-plan.md`](plans/math-plan.md)
- [`plans/ui-design-plan.md`](plans/ui-design-plan.md)

Implementation docs:

- [`docs/formulas.md`](docs/formulas.md)
- [`docs/api.md`](docs/api.md)
- [`docs/deployment.md`](docs/deployment.md)
- [`docs/review-notes.md`](docs/review-notes.md)

## Security / licensing note

This repository is public for transparency and collaboration, but no open-source license has been granted yet. Until a `LICENSE` file is added, all rights are reserved except GitHub's normal viewing/forking terms.

Do not use this for automatic chemical dosing. The initial scope is calculation, logging, export, and dashboarding only.
