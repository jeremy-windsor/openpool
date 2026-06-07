# Security Policy

## Current status

This project is in planning stage. Do not deploy it as a public internet service yet.

## Safety boundaries

`openpool` is intended for logging, calculation, dashboarding, and export. It is not intended for automatic chemical dosing or closed-loop control.

## Data handling goals

- Store data locally in SQLite.
- Keep write endpoints private/authenticated before public exposure.
- Keep share endpoints read-only.
- Do not expose private notes through share JSON unless explicitly configured.
- Do not store secrets in exports.

## Reporting vulnerabilities

Open a GitHub issue for non-sensitive reports. For sensitive reports, contact the repository owner privately.
