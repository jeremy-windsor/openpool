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

Planning stage. No production code yet.

See:

- [`plans/openpool-plan.md`](plans/openpool-plan.md)

## Security / licensing note

This repository is public for transparency and collaboration, but no open-source license has been granted yet. Until a `LICENSE` file is added, all rights are reserved except GitHub's normal viewing/forking terms.

Do not use this for automatic chemical dosing. The initial scope is calculation, logging, export, and dashboarding only.
