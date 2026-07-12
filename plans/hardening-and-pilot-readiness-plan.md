# openpool hardening and pilot-readiness plan

Date: 2026-07-11 (revised same day after adversarial review and PM adjudication)

This is the companion to [`openpool-plan.md`](openpool-plan.md),
[`math-plan.md`](math-plan.md), [`ui-design-plan.md`](ui-design-plan.md),
[`phase-3-chemistry-logbook-core.md`](phase-3-chemistry-logbook-core.md), and
the durable [`project-tracker.md`](project-tracker.md). It converts the
verified security, chemistry-safety, data-integrity, UX, documentation, CI,
and deployment findings into named, executable milestones with release gates.

It deliberately uses **named milestones** instead of another "Phase N" — the
existing plans already use phase numbers three different ways, and this plan
should not add a fourth.

## Decision

**Do not use openpool's dosing recommendations on a real pool, and do not
widen its exposure, until the release gates below pass.**

Specifically:

- **Recommendation use is blocked** until **Gate P (pilot-ready)** passes.
  The verified defects below can produce repeated, stale, understated, or
  wrongly-scaled doses. Until Gate P, the calculator and dashboard
  recommendations are development output, not pool-care advice.
- **Logging may continue, local/testing-only.** Using the app as a logbook
  (readings, additions, maintenance) is fine and produces useful pilot data.
  Logging-only test use may run on a trusted LAN/VLAN, **with the explicit
  risk understood**: every write endpoint is open to every client on that
  network until authentication exists. Doses added to a real pool must be
  decided from the product label and an independent reference, then logged
  after the fact.
- **The recommendation-following pilot itself (after Gate P) runs on
  loopback, an SSH tunnel, or a private VPN only.** Because the app has no
  authentication until Gate X, "trusted LAN/VLAN" is not an acceptable
  posture for a deployment whose advice someone is following: any device on
  that LAN can silently edit the readings the recommendations are computed
  from. LAN-wide use waits for authentication.
- **Exposure beyond that** — anything public or semi-public — is blocked
  until **Gate X (public-exposure-ready)** passes. This restates and
  strengthens the standing rule in `docs/deployment.md` and the container
  policy in `openpool-plan.md`.
- The pilot checklist in `docs/deployment.md` is **suspended for
  recommendation-following** until Gate P and will be rewritten (not merely
  amended) as part of this plan; its logging and backup steps remain valid
  in the meantime.

Architecture is not in question. FastAPI + Jinja2 + SQLite, server-rendered,
local-first, one container, one `/data` volume. No SPA, no automatic dosing,
no closed-loop control, no new integrations or charts before the gates pass.

## Verified baseline (2026-07-11, commit `436d21c`)

Two kinds of evidence, kept distinct.

**Independently re-verified against the local working tree:**

- **Tests:** 101 passed, 2 skipped (the PostgreSQL parity tests skip without
  `OPENPOOL_TEST_DATABASE_URL`). `uv run ruff check .` passes.
- **Local lockfile:** `uv.lock` pins **Starlette 1.2.1**, a vulnerable
  release. `Dockerfile` line 20 installs from `pyproject.toml` ranges
  (`pip install '.[postgres]'`), ignoring the lock, so image contents are
  resolved fresh at build time and are not reproducible. CI likewise
  installs unlocked (`uv pip install -e ".[dev]"`).
- Every defect file/line reference below was re-checked in the working tree
  at `436d21c`.

**Accepted external audit evidence (not re-derivable from the local tree;
treated as trusted inputs from the completed security review):**

- The published `ghcr.io/jeremy-windsor/openpool:latest` image had **zero
  Trivy high/critical findings** and shipped **Starlette 1.3.1** — meaning
  the image is only clean because the unlocked build happened to resolve a
  fixed version. The clean scan is luck, not control.
- Gitleaks found no secrets in the repository.
- `main` has **no branch protection**, and **Dependabot alerts and updates
  are disabled** in the repository settings.

## Safety policies

Named, objective rules that milestones, the defect matrix, and the gates
reference. Each policy is implemented as code plus tests; a gate condition
that references a policy means "the policy's tests exist and pass."

- **SP-1 — Fresh Reading Policy.** An FC or SLAM dose recommendation may be
  produced only when **all** of the following hold, evaluated in the pool's
  configured timezone:
  1. the latest reading is **no more than 12 hours old**, and
  2. the reading was taken on the **current local calendar day**, and
  3. **no chlorine-type addition (SP-2)** was logged after the reading's
     `tested_at`.
  Otherwise the app emits a **retest-only** action (severity `retest`, no
  dose amount, reason stated). The 12-hour constant and the calendar-day
  rule live as named module-level policy constants with their own tests —
  no magic numbers inside functions.
- **SP-2 — Canonical chlorine-addition set.** The chemicals that count as
  "chlorine was added" are exactly
  `{"liquid_chlorine", "trichlor", "dichlor", "cal_hypo"}`, defined once as
  a shared constant (proposed home: `openpool/chemistry/chlorine.py`,
  imported by `services.py`). There is no `bleach` chemical anywhere in the
  codebase and none is invented. Unknown or free-text chemical names do
  **not** suppress recommendations unless they are explicitly added to this
  set.
- **SP-3 — Strength semantics.** Product strengths are **percent-only in
  `[1, 100]`**. Exactly `1` means 1 %. Values in `(0, 1)` are refused as
  ambiguous fractional notation ("enter product strength as a percent,
  e.g. 10 for a 10% product"). Values `<= 0` or `> 100` are refused as
  impossible. Product-specific supported ranges remain **stricter** where
  known (muriatic acid: only the supported product strengths; cal-hypo,
  liquid chlorine: plausibility warnings on their typical label ranges).
  There is no fraction reinterpretation anywhere.
- **SP-4 — Finite input and output.** Every chemistry entrypoint validates
  that every numeric argument is finite before computing, **and** every dose
  result is checked finite (amount, secondary values, effects, stage
  amounts) before it is serialized or rendered. A `nan`/`inf` input **or
  output** produces an inline form error or API 400 refusal and **no dose
  card** — "no 500" is not the bar; "no number reaches the user" is.
- **SP-5 — Dilution-zero refusal.** A dilution target of exactly zero is
  refused, never answered. Exact zero is unreachable by partial dilution,
  and complete water replacement carries structural, hydrostatic, and
  equipment risks that require a site-specific safe-drain plan. openpool
  does not prescribe full drains. The refusal says so and tells the user to
  enter a positive target or consult qualified local guidance. The refusal
  is a `ValueError`/domain refusal in chemistry, surfaced as an API 400 and
  an inline page error.
- **SP-6 — Offline safety scope.** Navigation, chemistry, dashboard, and
  history responses are **network-only**. Offline, the service worker
  serves a **branded offline safety page** containing no cached private
  data: no readings, no history, no recommendations, no dose cards. No
  offline writes. (A timestamped read-only offline snapshot is a separate
  post-P design decision — see Pilot Ergonomics.)
- **SP-7 — Exposure policy.** Until Gate X: recommendation-following use is
  loopback/SSH-tunnel/private-VPN only; logging-only test use may be
  trusted-LAN with the open-writes risk documented; nothing is ever
  public-facing.

## Verified defects vs design debt

The two categories get different treatment. **Verified defects** are behaviors
that contradict the app's own documented rules ("every approximate formula
says it is approximate", "no recommendation should hide unit assumptions",
"missing inputs do not create fake precision") or crash. They get a refusal or
guardrail behavior plus a regression test, and they gate releases.
**Design debt** is work the plans knowingly deferred; it gets scheduled, not
treated as a betrayal.

### Verified defects

| ID | Where | What happens today |
|----|-------|--------------------|
| D1 | `openpool/services.py:278` (`recommended_actions`), `openpool/services.py:316` (`status_summary`), `openpool/services.py:334` (`build_snapshot`) | The dashboard recommends a full FC dose from the latest reading regardless of the reading's age and regardless of chlorine additions logged after it. Every page load repeats the same dose. A user who dosed an hour ago and reloads is told to dose again. |
| D2 | `openpool/chemistry/targets.py:65-72` (`round_cya_bucket`) | CYA above the chart (>100 liquid chlorine, >80 SWG) silently clamps to the highest bucket with only a warning string. SLAM and maintenance FC targets are understated for exactly the pools where getting them wrong matters most. |
| D3 | `openpool/chemistry/units.py:43-50` (`normalize_percent`) | Strength `<= 1` is reinterpreted as a fraction: entering `1` for a 1 % product becomes 100 %, entering `0.5` becomes 50 %. The boundary is ambiguous and the reinterpretation is silent, so a dose can be wrong by orders of magnitude with no warning. There is also no upper bound; `strength=250` is accepted. |
| D4 | `openpool/services.py:228-237` (`lower_ph` branch), `openpool/templates/calculator.html:69-71` | `dose_muriatic_acid_for_ph` supports 31.45 % and 14.5 % acid (`openpool/chemistry/acid_base.py:26-29`), but the service layer never passes a strength and the calculator UI only shows the strength field for `raise_fc`/`slam_fc`. A 14.5 % acid user gets a 31.45 % dose volume, silently under-dosing by roughly half, and any `strength` sent to the API for `lower_ph` is ignored. |
| D5 | `openpool/chemistry/operations.py:52` (`estimate_drain_for_dilution`) | `target_ppm=0` passes the schema (`CalculationIn.target` is `ge=0`) and the function's guards, then crashes with `ZeroDivisionError` in `log(current_ppm / target_ppm)`. "Drain until CYA is 0" is a legitimate question; the answer is a 500. |
| D6 | `openpool/schemas.py:57` and `:66` (`ReadingIn.tc`, `.csi`), `openpool/db.py:530-533` (`create_reading`), `openpool/db.py:588-594` (`update_reading`) | API clients can store arbitrary `tc` and `csi` values that contradict the reading's own components. The server only computes them when the client leaves them out. Derived values are not server-owned. |
| D7 | `openpool/db.py:504-514` (`_computed_csi`) | `calculate_csi` returns warnings ("No CYA reading; correction skipped", "assuming 80 F") and the DB layer throws them away, storing only the bare number. History and share JSON present a defaulted-input CSI with the same confidence as a fully-measured one, and there is no record of which inputs produced it. |
| D8 | `openpool/db.py:685` (`create_addition`), `openpool/db.py:717-726` (`update_addition`) | `linked_reading_id` accepts any existing reading id, including a reading from a different pool. The FK (`openpool/db.py:125`) only checks existence. Cross-pool links corrupt the cause/effect chain the logbook exists to preserve. |
| D9 | `openpool/schemas.py:51-137`, `openpool/routers/pages.py:340-347` (`_parse_optional_float`) | Validation gaps: `water_temp_f` and `csi` are unbounded; `fc`/`ta`/`ch`/`cya`/`salt` accept absurd values; strength fields accept >100; the calculator page path parses floats with bare `float(raw)`, so `nan` and `inf` flow into chemistry functions (the `isfinite` check in `openpool/db.py:393-396` only protects DB writes) and nothing checks the **outputs** for finiteness before rendering. No product-specific plausibility checks exist. |
| D10 | `openpool/routers/pages.py:81-90` and all `save_*` handlers | Any validation error raises `HTTPException(400)`, replacing the form with a bare error response. Everything typed poolside is lost. This is a safety issue, not just annoyance: retyping under time pressure produces entry mistakes in a chemical log. |
| D11 | `.github/workflows/docker.yml:11-13`, unpinned `uses:` lines throughout; `Dockerfile:1` and `:20`; `uv.lock` | Workflow-level `packages: write` applies to the PR-triggered test job; all actions are tag-pinned, not SHA-pinned; the base image is not digest-pinned; neither CI nor the image build uses `uv.lock` (which is itself stale and vulnerable — see baseline). Builds are neither reproducible nor least-privilege, and no dependency or image scanning runs in CI. |
| D12 | `openpool/db.py:282-285` (`init_db`), `SCHEMA` at `:69-152` | The only schema mechanism is `create table if not exists`. Any future column or constraint silently does not apply to existing databases. There is no schema version and no schema migration path (`openpool/migrate.py` is a SQLite-to-Postgres **copier**, not a schema migrator — and it must be updated in lockstep whenever columns change, or it silently drops data). Almost no CHECK constraints exist beyond `volume_gallons > 0`. |

### Design debt (known, deferred, now scheduled)

- **No authentication, sessions, or API tokens** — documented in
  `docs/review-notes.md`, `plans/next-steps.md` (DeepSec item 1), and the
  tracker's Active Concerns. Write APIs are open to any client that can reach
  the service.
- **Weak CSRF story** — `openpool/security.py:23-31` rejects cross-origin
  writes only when an `Origin`/`Referer` header is present and mismatched,
  compares against the unvalidated `Host` header, and there is no trusted-host
  allowlist, no request-body size limit, and no rate limiting.
- **Share tokens** — stored plaintext in SQLite, re-displayed in the settings
  form (`openpool/templates/settings.html:44`), and passed as URL query
  parameters. URL tokens **inherently** appear in URLs, access logs, and
  referrers — that is a property of the transport, not a bug to promise away.
  The Gate X token policy below picks an explicit stance. DeepSec item 2.
- **No native backup/restore path** — `all.json` is a portable export, not a
  disaster-recovery mechanism: it has no schema version, and nothing can
  restore it. There is no documented, verified database-level backup.
- **PostgreSQL is untested in CI** — the 2 parity tests always skip there.
- **Metric mode is stored but not implemented** — `unit_system` is a settings
  toggle with zero effect on inputs, math, or exports (tracker Active
  Concerns).
- **Mobile UI slices 2-5 unbuilt** — add-reading steppers/validation (2),
  calculator polish (3), history stacked rows (4), settings/share styling (5)
  per the tracker's "Pending UI slices". Slices 2 and 4 are scheduled post-P
  below; **slices 3 and 5 remain deferred** with no date.
- **Accessibility target is WCAG 2.1 AA on paper, unaudited in practice** —
  `ui-design-plan.md` §8; this plan raises the target to **WCAG 2.2 AA**,
  audited post-P.
- **PWA scope** — `static/sw.js` exists with a "no stale chemistry HTML" rule
  from the first review; SP-6 turns that into an enforced, tested invariant.
- **Borates dosing** — per `math-plan.md` §8, borates are "required for v1
  **data model** and v2 **calculator behavior**". The v1 data-model half
  (storage, export, CSI correction) is implemented; the dose calculation is
  v2 calculator behavior and remains unbuilt. This is a deferral to record,
  not a missed v1 requirement.
- **Docs drift** — `project-tracker.md` tells readers to read a nonexistent
  `AGENTS.md`; `README.md` still opens with "planned shape"; `docs/api.md`
  predates the Phase 3 CRUD endpoints; `plans/next-steps.md` stacks a
  2026-06-28 security section on top of a 2026-06-07 handoff; the pilot
  checklist in `docs/deployment.md` predates this plan's decision and needs
  a rewrite, not a patch.

## Defect matrix

Severity scale: **S1** — can produce a wrong or unsafe chemical action, or
crashes a dosing path. **S2** — corrupts or misrepresents stored data.
**S3** — security exposure. **S4** — usability/process failure that causes
S1/S2-adjacent mistakes.

Gate column: **P** must be fixed before Gate P (pilot-ready);
**X** must be fixed before Gate X (public-exposure-ready). Everything gated P
is implicitly gated X.

| ID | Sev | Observed behavior | Invariant after fix | Gate |
|----|-----|-------------------|---------------------|------|
| D1 | S1 | Same full FC dose re-recommended on every load, regardless of reading age or later logged additions | SP-1 holds at every surface that renders recommendations (dashboard, status, share): a dose appears only for a fresh same-day reading with no subsequent SP-2 chlorine addition; otherwise a `retest` action with no amount | P |
| D2 | S1 | Above-chart CYA silently clamps to the top bucket; SLAM/maintenance FC targets understated | Above-chart CYA produces a refusal with dilution guidance, never a numeric FC/SLAM target | P |
| D3 | S1 | Strength `<= 1` silently reinterpreted as a fraction; no upper bound | SP-3 holds: percent-only `[1, 100]`, exact 1 means 1 %, `(0,1)` refused as ambiguous, `<=0`/`>100` refused, product-specific ranges stricter where known | P |
| D4 | S1 | Acid dose always computed at 31.45 %; user/API strength silently ignored | Every dose reflects the product strength the user declared; unsupported strengths are refused with the supported list | P |
| D5 | S1 | Dilution to target 0 crashes with a 500 | SP-5 holds: target 0 is refused with the full-drain risk explanation at the chemistry, service, API, and page layers; no full drain is ever prescribed | P |
| D6 | S2 | Clients can store contradictory `tc`/`csi` on readings | `tc` and `csi` are server-computed, always; client-supplied values are rejected | P |
| D7 | S2 | CSI stored bare; its warnings and input assumptions discarded | Persisted derived values carry their warnings and input provenance, and the UI shows them | P |
| D8 | S2 | Additions can link readings from other pools | `linked_reading_id` must reference a reading in the same pool, enforced in the write path (and by constraint where the backend allows) | P |
| D9 | S2 | Non-finite and physically impossible values accepted on several paths; outputs never finiteness-checked | SP-4 holds at every chemistry entrypoint and before every serialization/render; all numeric inputs are inside documented physical bounds; product strengths inside product-specific ranges | P |
| D10 | S4 | Validation errors destroy the submitted form | Forms re-render with the submitted values and inline errors on every validation failure | P |
| D11 | S3 | Unlocked, unpinned, over-privileged build pipeline; stale vulnerable lockfile | Locked reproducible builds from `uv.lock`; SHA-pinned actions; digest-pinned base image; job-scoped permissions; dependency and image scanning in CI | P (lock refresh, locked CI install, permissions) / X (full) |
| D12 | S2 | No schema versioning or migration path; near-zero DB constraints; `migrate.py` copier not kept in lockstep | Every schema change ships as a versioned migration **and** updates `openpool/migrate.py` and the exports in the same slice, with copier/export/migration parity tests | P |
| — | S3 | No auth, open write APIs, weak CSRF, plaintext echoed share tokens, no rate/body limits | See Milestone "Locked Front Door" | X |

## Release gates

### Gate P — pilot-ready

Minimal, objective, and safety-focused. The app may be used to *follow*
dosing recommendations on one real pool by its owner — reached via
**loopback, SSH tunnel, or private VPN only** (SP-7) — when all of these
hold:

1. Defect matrix rows D1-D10 and D12, plus the D11 P-slice, are closed, and
   each has a **named regression test** committed and recorded in the
   tracker (the Safe Dosing milestone proposes the names).
2. Safety policies **SP-1 through SP-6** are implemented and tested at every
   entrypoint they name (chemistry function, service, API route, page
   route, service worker as applicable).
3. Critical chemistry fixtures exist for the D1-D5 behaviors and their
   refusal boundaries (Verified Chemistry, Gate P scope) — not the
   exhaustive every-formula expansion, which is post-P.
4. A **native backup/restore drill** has been performed and recorded: a
   SQLite online backup of the pilot database restored to a scratch
   location and verified readable by the app (Recoverable Data, Gate P
   scope).
5. Forms preserve user input on validation failure (D10), the offline
   safety page is in place (SP-6), and the settings page makes no false
   metric claims (Pilot Ergonomics, Gate P scope).
6. The supply-chain P slice is merged: refreshed `uv.lock` (Starlette
   ≥ 1.3.1), CI installs `--locked`, job-scoped workflow permissions,
   `persist-credentials: false`.
7. `docs/deployment.md` has its pilot checklist **rewritten** for this
   plan's rules, and the tracker/README state matches reality (Honest
   Paperwork, pilot-facing items).
8. The suite passes in CI, including the PostgreSQL parity tests or an
   explicit "experimental, not CI-covered" label on PostgreSQL everywhere
   it is mentioned.

Explicitly **not** required for Gate P (ordered post-P below): dose
provenance columns, staged-dose productization, CSV/`all.json` import
endpoints, the exhaustive fixture expansion, mobile add-reading/history
polish, and the full WCAG 2.2 AA audit.

### Gate X — public-exposure-ready

Strictly stronger than Gate P and testable. The app may be exposed beyond a
private tunnel (still behind a reverse proxy) when, in addition to Gate P:

1. Milestone **Locked Front Door** is complete: password/session auth with a
   **fail-closed bootstrap** (no unauthenticated setup race on non-loopback
   bindings), the full route-protection matrix, CSRF tokens, trusted-host
   enforcement, body-size limits, rate limiting with its process-model
   assumption enforced, and hashed API/share tokens with rotation and
   masked handling.
2. The **Gate X token policy** is in force: share access uses a bearer
   header or a **one-time exchange** (token URL redeems once, sets a
   short-lived cookie, and redirects to a token-free URL); persistent
   query-string token support is **disabled** in public mode. No persistent
   secret ever rides a query string. (Pre-X trusted-network deployments may
   keep `?token=` with the leakage risk documented.)
3. Milestone **Sealed Supply Chain** is complete, including branch
   protection on `main`, Dependabot alerts/updates enabled, and image plus
   dependency scanning gating the publish job.
4. A **written security review matrix** is completed and checked in (or
   attached to the tracker): every route × every principal
   (anonymous / session / API token / share token) with expected and
   observed results, **plus** the threat checklist below, each item marked
   *mitigated* (with the mitigation named and tested) or *accepted*
   (with the acceptance recorded in the tracker). "Reviewed in the same
   spirit as before" is not a criterion; the filled-in matrix is.
5. Reverse-proxy deployment guidance in `docs/deployment.md` is updated for
   the auth model and verified against a real proxy, including the
   config-aware secure-cookie behavior.

**Gate X threat checklist** (minimum; the review matrix may add more):

- **T1 — Calculator GET leakage.** `/calculator` (`openpool/routers/pages.py:391`)
  submits readings via GET, so water-chemistry values (and anything else the
  form ever grows) land in access logs and referrers. Mitigation: switch the
  calculator form to POST with `Cache-Control: no-store` on results, or
  record an explicit acceptance that chemistry values in logs are tolerable
  — and guarantee no credential or token can ever ride that URL.
- **T2 — Export exfiltration.** `/api/pools/{id}/export/*` returns the whole
  logbook in one request. Mitigation: exports require session/API-token
  auth (never share-token), are rate-limited, and appear in the route
  matrix explicitly.
- **T3 — First-run setup race.** An unauthenticated setup page on a
  non-loopback binding is a race anyone on the network can win. Mitigation:
  fail-closed bootstrap (Locked Front Door task 1) — verified by a test
  that binds non-loopback with no configured secret and observes a locked
  app.
- **T4 — Public share residual risk.** Share pages intentionally publish
  pool status; public exposure adds enumeration and caching risks.
  Mitigation: unguessable pool ids are not relied on (tokens gate access),
  `Cache-Control: no-store` and `Referrer-Policy: no-referrer` on share
  responses, notes and recommendations stay opt-in, rotation is one click,
  and the residual "whoever has the link sees pool status" risk is recorded
  as accepted.
- **T5 — Rate-limit process model.** The in-memory limiter only works in a
  single-process deployment. Mitigation: startup refuses or loudly warns
  when worker count > 1 with the in-memory limiter, and the deployment docs
  pin the single-process assumption; a shared-store limiter is out of scope
  until someone actually needs multiple workers.

Public exposure without Gate X remains unsupported, exactly as
`openpool-plan.md`'s container policy already states.

## Milestones

Ordered by user harm: wrong chemistry first, corrupted records second,
security third, everything else after. Milestones that span the gate are
split into an explicit **Gate P scope** and **post-P scope**. Each milestone
lists non-goals so scope cannot quietly grow back.

---

### Milestone: Safe Dosing

**Problem.** The five S1 defects (D1-D5) mean the calculator and dashboard
can repeat a dose, understate a SLAM target, misread a product strength by
100x, ignore the acid strength entirely, or crash. Additionally, nothing
tells the user to trust the product label over the app.

**Affected files.**

- `openpool/services.py` — `recommended_actions` (line 278),
  `status_summary` (316), `build_snapshot` (334), `calculate_goal`
  `lower_ph` branch (228-237), `slam_fc` branch (178-198)
- `openpool/chemistry/targets.py` — `round_cya_bucket` (53-72),
  `fc_cya_targets` (75-79)
- `openpool/chemistry/units.py` — `normalize_percent` (43-50)
- `openpool/chemistry/chlorine.py` — SP-2 constant home
- `openpool/chemistry/acid_base.py` — `dose_muriatic_acid_for_ph` (111-173),
  `ACID_PRODUCTS` (26-29)
- `openpool/chemistry/operations.py` — `estimate_drain_for_dilution` (12-68)
- `openpool/chemistry/dosing.py` — `Dose` (finite-output guard; staging
  fields are post-P, contract below)
- `openpool/schemas.py` — `CalculationIn` (113-137)
- `openpool/templates/calculator.html`, `openpool/templates/dashboard.html`,
  `openpool/templates/_reading_tiles.html`, `openpool/templates/share.html`
- `tests/test_chemistry.py`, `tests/test_api.py`,
  `tests/fixtures/public_reference_examples.json`

**Gate P scope — implementation tasks.**

1. **Fresh Reading Policy (D1 / SP-1) with an explicit call graph.**
   - Policy constants in `services.py` (or a small `policies.py`):
     `RECOMMENDATION_MAX_READING_AGE_HOURS = 12` plus the same-local-
     calendar-day rule, evaluated in the pool timezone.
   - `recommended_actions(pool, reading, additions_since_reading)` takes the
     evidence as a parameter — **preferred**: the caller passes the list of
     additions logged at or after the reading's `tested_at`; alternatively
     an overload accepting `(conn, pool_id)` may fetch them itself, but the
     pure-data signature is what gets unit-tested.
   - `build_snapshot` fetches the evidence once via
     `db.list_additions(conn, pool_id, start_utc=reading["tested_at"])`
     (the parameter already exists — `openpool/db.py:747-773`) and passes
     the **same** evidence to `recommended_actions`, `status_summary`, and
     the share snapshot, so the dashboard, status banner, and share page can
     never disagree about whether a dose is fresh.
   - Suppression consults **only** the SP-2 canonical set. `bleach` does not
     exist and is not added; unknown chemical strings never suppress.
   - **Retest-only severity:** suppressed recommendations are emitted with
     `severity: "retest"` and no `dose` payload; `status_summary` maps it to
     a caution-level "Retest before dosing" banner; templates render it with
     no amount anywhere. This severity value is part of the API surface and
     is tested.
2. **Unambiguous strength (D3 / SP-3).** `normalize_percent` implements
   SP-3 exactly: accept `[1, 100]`, `1` means 1 %, refuse `(0, 1)` as
   ambiguous fractional notation with the example message, refuse `<= 0`
   and `> 100` as impossible. Update every caller and any fixture that used
   the `0.10` form. Product-specific plausibility warnings (typical label
   ranges) layer on top in Trustworthy Records task 5.
3. **CYA above-table refusal (D2).** `round_cya_bucket` returns a refusal
   sentinel (not the top bucket) when CYA exceeds the highest supported row
   (100 for liquid chlorine, 80 for SWG). `fc_cya_targets` propagates it;
   `slam_fc` and `recommended_actions` render "CYA {value} is above the
   supported FC/CYA chart — lower CYA by water replacement before dosing
   from this chart" with a link to the `lower_by_dilution` goal. Keep the
   existing conservative round-up for in-table values and the lowest-bucket
   fallback for missing CYA (both are already tested behavior).
4. **Acid strength honored (D4).** The `lower_ph` branch of `calculate_goal`
   passes `acid_percent=values["strength"]` when provided (default 31.45).
   `calculator.html` shows a strength control for `lower_ph` as a select of
   the supported strengths (31.45 %, 14.5 %) so unsupported free-text never
   reaches the API from the UI; the API keeps the existing supported-list
   refusal in `dose_muriatic_acid_for_ph` for direct callers. The dose card
   labels the strength it used.
5. **Dilution target zero (D5 / SP-5).** `estimate_drain_for_dilution`
   raises `ValueError` for `target_ppm <= 0` with the SP-5 refusal text:
   exact zero is unreachable by partial dilution; complete water replacement
   carries structural, hydrostatic, and equipment risks and needs a
   site-specific safe-drain plan; openpool will not prescribe it; enter a
   positive target or consult qualified local guidance. The service layer
   passes it through; the API returns 400; the calculator page renders it as
   an inline error. **No code path recommends a 100 % drain.** No code path
   divides by the target.
6. **Finite input/output guard (SP-4).** Every public function in
   `openpool/chemistry/` validates its numeric arguments finite on entry
   (a small shared helper). `Dose` gains a validation step (called from
   `to_dict()` or by the service before serializing) that refuses
   non-finite `amount`, `secondary`, `effects`, and stage values.
   `_parse_optional_float` in `pages.py` rejects `nan`/`inf` with the
   inline-error path. A non-finite value anywhere yields a refusal and no
   dose card — at the chemistry, service, API, and page layers.
7. **Label-first warning.** Every dose result leads with a standing
   warning: "Follow the product label; it overrides this calculation."
   (One-line addition to the dose pipeline; the larger staged-dose feature
   is post-P, below.)

**Named regression tests (proposed; final names recorded in the tracker):**

- D1: `test_recommendation_requires_fresh_same_day_reading`,
  `test_recommendation_suppressed_after_chlorine_addition`,
  `test_unknown_chemical_does_not_suppress_recommendation`,
  `test_retest_severity_has_no_dose_amount`,
  `test_share_and_dashboard_agree_on_retest` (service + API + page).
- D2: `test_cya_above_table_refuses_maintenance_and_slam` (chemistry +
  service + API).
- D3: `test_strength_one_means_one_percent`,
  `test_strength_fractional_notation_refused`,
  `test_strength_out_of_range_refused` (chemistry + API + page).
- D4: `test_lower_ph_uses_declared_acid_strength`,
  `test_unsupported_acid_strength_refused_with_supported_list`
  (chemistry + service + API + page).
- D5: `test_dilution_target_zero_refused_chemistry`,
  `test_dilution_target_zero_api_400`,
  `test_dilution_target_zero_inline_page_error` (all four layers).
- SP-4: `test_nan_input_refused_no_dose_card`,
  `test_nonfinite_dose_output_never_serialized`.

**Acceptance criteria.**

- Every D1-D5 behavior is observable in the running app (manual check via
  `/calculator` and `/`), and each named regression test fails on the
  pre-fix code.
- No calculator input reachable from the UI or the JSON API can produce a
  500 **or a non-finite number** from the chemistry layer.
- No refusal is silent: each one states why and what to do instead
  (matching the "never alarm without a remedy" rule in
  `ui-design-plan.md` §2.5).
- Dose metadata (formula, source note, assumptions, confidence) is unchanged
  or improved — never dropped by the new paths.

**Post-P scope — staged-dose productization.** Split out from D1 by review:
for large single doses (proposed thresholds to confirm: FC raise > 10 ppm
outside SLAM, pH move > 0.4, TA raise > 40 ppm, CH raise > 100 ppm), the
result recommends portioned addition. **`Dose` contract:** three new fields
with defaults so every existing constructor call is untouched —
`staged: bool = False`, `stage_amount: float | None = None`,
`stage_note: str | None = None` (stage amount is in the same `unit` as
`amount`). `to_dict()` adds `"staged"`, `"stageAmount"`, `"stageNote"`.
**Rendering contract:** when `staged` is true, the calculator result card
and recommendation card show `stage_amount` as the headline actionable
amount with the total as context ("Total ≈ {amount} {unit}; add no more
than {stage_amount} now, circulate 30-60 min, retest, repeat"), and
"Log this dose" prefills the stage amount, not the total. Stage values pass
the SP-4 finite guard like everything else.

**Dependencies.** None. This milestone goes first; within it, D3 and D1
land first (build sequence below).

**Non-goals.** No new chemistry formulas (no borates dosing), no automatic
dose logging, no reworking the FC/CYA table values themselves, no UI
redesign beyond the strength select and refusal/retest rendering.

---

### Milestone: Trustworthy Records

**Problem.** Derived values are client-writable (D6), their provenance is
discarded (D7), additions can link foreign readings (D8), validation has
holes (D9), and the schema has no versioning or constraints (D12) — and the
SQLite-to-Postgres copier plus the CSV/JSON exports silently drift whenever
columns change. A logbook that cannot defend its own records is decoration.

**Affected files.**

- `openpool/db.py` — `SCHEMA` (69-152), `init_db` (282-285),
  `_clean_payload` (386-400), `_computed_csi` (504-514), `create_reading`
  (517-561), `update_reading` (569-604), `create_addition` (658-696),
  `update_addition` (704-736), `READING_FIELDS` (174-190)
- `openpool/migrate.py` — the Postgres copier: **updated in the same slice
  as every schema change**, with parity tests
- `openpool/schemas.py` — `ReadingIn` (51-68), `AdditionIn`/`AdditionUpdate`
  (71-94), `CalculationIn` (113-137), `PoolIn`/`PoolUpdate`
- `openpool/routers/pages.py` — `save_reading_edit` `drop=` handling (141)
- `openpool/routers/api.py`, `openpool/routers/export.py` (new columns in
  exports), `openpool/templates/history.html`,
  `openpool/templates/_reading_tiles.html`
- `tests/test_persistence.py`, `tests/test_api.py`, `tests/test_postgres.py`,
  `docs/api.md` (breaking-change note)

**Gate P scope — implementation tasks.**

1. **Migrations scaffold first (D12).** Add a `schema_version` table (works
   identically on SQLite and PostgreSQL, unlike `PRAGMA user_version`) and an
   ordered list of migration functions in `db.py`. `init_db` creates fresh
   schema at the latest version or applies pending migrations in a
   transaction. Keep it boring: no Alembic, no new dependency. Tests cover
   fresh-create and upgrade-from-v0 paths on both backends. **Standing rule
   established here:** any slice that adds or changes a column must, in the
   same slice, (a) ship the migration, (b) update `openpool/migrate.py`'s
   copier column lists, (c) update the CSV/JSON exports, and (d) extend the
   **parity test** that asserts migration output, copier output, and export
   columns agree.
2. **Server-owned TC and CSI (D6).** Remove `tc` and `csi` from `ReadingIn`
   and from `READING_FIELDS`' writable set. `create_reading`/`update_reading`
   always compute `tc = fc + cc` (when both present, else NULL) and always
   recompute CSI. Because `ReadingIn` uses `extra="forbid"`, old clients
   sending `csi` get a 422 — document this as a breaking change in
   `docs/api.md`. The page edit path already drops these
   (`pages.py:141`); simplify it once the schema no longer accepts them.
3. **Persisted CSI provenance (D7).** Via a migration (rule 1 applies: same
   slice updates `migrate.py` and exports), add
   `test_readings.csi_meta_json`: the `CsiResult` warnings, the inputs used
   (including which defaults were assumed), and a formula version string.
   Dashboard tiles, history, and share JSON surface the warnings ("CSI
   assumed 80 °F — log water temperature for a better estimate") instead of
   presenting defaulted CSI as measured.
4. **Cross-pool link integrity (D8).** `create_addition` and
   `update_addition` verify the linked reading exists **and** belongs to the
   same `pool_id`, raising `ValueError` otherwise. Add the check at the
   write path (works on both backends today); add a composite
   `(id, pool_id)` unique index plus composite FK in a migration where the
   backend supports it. Regression tests on SQLite and in the Postgres
   parity suite.
5. **Finite, physical, product-specific validation (D9 / SP-4).**
   - Pydantic bounds: document and enforce hard physical bounds — proposed:
     `fc`/`cc` 0-100 ppm, `ta`/`ch` 0-2000, `cya` 0-500, `salt` 0-50000,
     `borates` 0-200, `ph` 0-14 hard (the 6.0-8.9 "unusual" band is a UI
     warning per `ui-design-plan.md` §5.2, not a refusal), `water_temp_f`
     32-120, `filter_pressure` 0-100, `strength`/`strength_percent`/
     `default_chlorine_percent` per SP-3, `pool_gallons`/`volume_gallons`
     up to 1,000,000, `amount` up to 100,000.
   - Product-specific ranges as **warnings** on dose results (liquid
     chlorine typically 3-15 %, cal-hypo 35-78 %): warn outside, refuse only
     the impossible per SP-3.
   - Every bound gets a one-line rationale comment and a test at both edges.
   - (The `_parse_optional_float` finite fix and the output-side guard land
     in Safe Dosing task 6; this task completes the input-bounds sweep.)
6. **DB constraints.** In the same migrations: CHECK constraints mirroring
   the hard bounds for the core columns SQLite/Postgres share
   (non-negative concentrations, `ph between 0 and 14`, `amount > 0`),
   NOT NULL where the app already guarantees it. SQLite CHECK additions
   require a table rebuild — that is exactly what the migration scaffold is
   for. Constraints are the backstop; Pydantic remains the front line with
   better messages.

**Post-P scope — dose provenance.** Via migration (rule 1 applies), add
`chemical_additions.calculation_json` and
`chemical_additions.expected_effects_json` (nullable — both anticipated in
`phase-3-chemistry-logbook-core.md` Data Model Notes). When a dose is logged
from a calculator result, the addition form carries the full dose payload
(chemical, amount, unit, strength, formula, source note, assumptions,
effects, app version) in a hidden field; the server validates shape and size
(cap at 8 KB) and stores it. Manually-entered additions leave both NULL.
History row detail and `all.json` expose them. Useful, durable, and **not a
pilot blocker** — the pilot's provenance is the calculator metadata already
shown at dose time.

**Acceptance criteria (Gate P scope).**

- A client cannot cause the DB to store a `tc`, `csi`, or cross-pool link
  that the server did not compute or verify — proven by tests that try.
- Editing a reading recomputes both `tc` and CSI and refreshes
  `csi_meta_json` (extends the existing recompute-on-edit behavior).
- A pre-milestone SQLite file upgrades in place with data intact
  (round-trip test on a fixture DB), **and** `openpool-migrate` copies every
  current column to Postgres, **and** exports carry every current column —
  asserted by one parity test that fails if any of the three drifts.
- Every hard bound refuses with a message naming the field and the allowed
  range; every soft bound warns without blocking.
- Exports still pass the CSV formula-injection escaping tests.

**Dependencies.** Migrations scaffold (task 1) blocks tasks 3, 4 (constraint
half), 6, and the post-P provenance work. Safe Dosing's SP-3 feeds the
validation bounds here.

**Non-goals.** No `users` table, no `pool_settings_history`, no
`target_profiles` (unchanged from the tracker's Moved Later), no audit log
beyond the provenance columns, no reworking the UUID id scheme.

---

### Milestone: Verified Chemistry

**Problem.** The math plan demands independent validation ("no mystery
constants", fixtures with source notes). The pilot needs the **critical**
slice of that — independent fixtures for exactly the behaviors that were
broken (D1-D5) and their refusal boundaries — while the exhaustive
every-formula expansion is real work that should not block the pilot.

**Affected files.**

- `tests/fixtures/public_reference_examples.json` (extend; keep shape)
- `tests/test_chemistry.py`
- `docs/formulas.md` (derivation notes)
- No production code except where a fixture exposes a real discrepancy.

**Gate P scope — implementation tasks.**

1. **Critical fixtures for D1-D5.** Independently derived (hand calculation
   written out in `docs/formulas.md`, cross-checked against a public
   reference, per the clean-implementation rule in `math-plan.md`):
   - the 14.5 % vs 31.45 % acid dose ratio (D4),
   - strength boundary cases: 1 % accepted as 1 %, 0.5 refused, 101 refused
     (D3),
   - CYA 110 (liquid chlorine) and CYA 90 (SWG) refuse targets/SLAM (D2),
   - dilution target 0 refused; a positive-target dilution case with the
     known proportional answer (D5),
   - a fresh-vs-stale recommendation pair pinning SP-1's 12-hour and
     calendar-day boundaries, including the boundary just inside and just
     outside (D1).
2. **Property tests (corrected by review).** For acid and soda-ash dosing:
   **monotonicity** (a larger pH move in the same direction never yields a
   smaller dose), **volume linearity** (double the volume, double the
   dose), and **TA-effect sign** (`effects["ta"]` is negative for muriatic
   acid, positive for soda ash). No symmetry property is asserted — acid
   demand and base demand are not mirror images of each other and the suite
   must not pretend they are. For the mass/ppm doses: linearity in volume
   and in delta; dilution round-trip (`current * (1 - fraction) == target`).
3. Tolerances per `math-plan.md`: 1-2 % for mass/ppm dosing; documented
   wider tolerances for pH/CSI with the assumption set named in the fixture.
4. Record any fixture that the implementation fails as a finding first —
   do not tune the fixture to the code.

**Post-P scope — exhaustive expansion.** ≥2 independent fixtures for every
remaining formula in `openpool/chemistry/` (chlorine dry products, CYA,
salt, calcium, alkalinity, CSI, SWG runtime), each with `source_note`,
`tolerance_percent`, and a derivation in `docs/formulas.md` complete enough
for a competent reader to recompute each constant by hand.

**Acceptance criteria (Gate P scope).** Every D1-D5 fixture and property
test above exists and passes; each derivation is written in
`docs/formulas.md`; no fixture was fitted to the implementation.

**Dependencies.** Safe Dosing (fixtures target the post-refusal behavior).

**Non-goals.** No new formulas, no borates dosing (a v2 calculator behavior
per `math-plan.md` §8 — see Honest Paperwork), no comparison harness against
proprietary calculators.

---

### Milestone: Recoverable Data

**Problem.** There is no verified way to recover the pilot's database.
`all.json` looks like a backup but is not one: it has no schema version, no
restore path, and no guarantee of completeness as columns change. A pilot
that cannot recover its data after a bad container move is a data-loss
incident on a timer. Recovery for the pilot must be **native and boring**;
product import features come later.

**Affected files.**

- `openpool/db.py` (backup helper), `pyproject.toml` (console script)
- `docs/deployment.md` (backup/restore procedure, restore drill)
- `openpool/templates/settings.html` / `history.html` (relabel export
  buttons), `docs/api.md`
- Post-P: new `openpool/routers/importers.py`, `openpool/schemas.py`
  (import payloads), `tests/test_import.py`

**Gate P scope — implementation tasks.**

1. **Native SQLite backup.** An `openpool-backup` console script (stdlib
   `sqlite3.Connection.backup` — WAL-safe, consistent, no new dependency)
   that writes a timestamped copy of the live database, plus the documented
   equivalent `sqlite3 /data/openpool.sqlite ".backup ..."` invocation for
   operators who prefer the CLI. Documented in `docs/deployment.md`.
2. **Verified restore drill.** A documented, rehearsed procedure: back up,
   restore to a scratch path, point a scratch container at it, verify the
   app reads it (`/api/health`, dashboard, history row counts). Gate P
   requires the drill to have been **performed and recorded**, not just
   written down.
3. **PostgreSQL.** If the deployment uses Postgres, the documented path is
   standard `pg_dump`/`pg_restore` with the same drill. If Postgres ends up
   labeled experimental (Sealed Supply Chain task 3), the docs say backup
   support follows the same label.
4. **Relabel `all.json`.** Everywhere it appears (settings, history,
   `docs/api.md`, deployment docs), `all.json` is a **portable export** for
   inspection and interchange — explicitly *not* the disaster-recovery
   mechanism. It gains a schema-version field only when the post-P import
   work makes it round-trippable.

**Post-P scope — product import.**

- `all.json` completeness/versioning plus a restore endpoint
  (`POST /api/pools/{pool_id}/import/all.json`) with dry-run report,
  transactional apply, id preservation, and explicit conflict policy
  (`skip` default, `replace` opt-in).
- CSV import for readings and additions matching the export columns, same
  dry-run/commit flow, all rows passing the same validation as API writes.
- Server-owned fields (`tc`, `csi`, `csi_meta_json`) recomputed on import,
  never trusted from the file; cross-pool link rejection applies (D8).
- Import endpoints are authenticated write endpoints once Locked Front Door
  lands.

**Acceptance criteria (Gate P scope).** A backup taken during the drill
restores to a working app with identical row counts; the procedure is in
`docs/deployment.md`; no UI or doc calls `all.json` a backup.

**Dependencies.** None for the Gate P scope (deliberately — recovery must
not wait on schema work). Post-P import depends on Trustworthy Records.

**Non-goals.** Hosted-app import, scheduled backups, incremental sync,
multi-file archives.

---

### Milestone: Pilot Ergonomics

**Problem.** Form errors destroy input (D10); offline behavior must never
serve stale chemistry (SP-6); and the metric toggle is a stored lie. Those
three make a pilot produce bad data — they gate. The poolside UI polish and
the accessibility audit are valuable and scheduled, but a pilot on the
current plain forms is safe, just unglamorous — they do not gate.

**Affected files.**

- Gate P: `openpool/routers/pages.py` — every `save_*` handler (81-90,
  130-148, 174-183, 208-226, 252-261, 286-302, 471-484);
  `openpool/templates/reading_form.html`, `addition_form.html`,
  `maintenance_form.html`, `settings.html`; `openpool/static/sw.js`,
  `manifest.webmanifest`, new offline page template/asset
- Post-P: `openpool/templates/history.html`, `base.html`,
  `openpool/static/app.css`, `app.js`, `tokens.css`;
  `plans/ui-design-plan.md` §8 (target note), `plans/project-tracker.md`
  (UI Build Status)
- `tests/test_api.py` (form re-render assertions), UI verification via the
  headless-screenshot flow already used for Slice 1

**Gate P scope — implementation tasks.**

1. **Form error preservation (D10).** Validation failures re-render the
   same template with the submitted values and per-field inline errors
   (status 422), never a bare `HTTPException` page. Applies to new **and**
   edit forms for readings, additions, maintenance, and settings. Follows
   the inline, non-blocking validation contract in `ui-design-plan.md`
   §5.2/§17.
2. **Offline safety page (SP-6).** `static/sw.js` treats navigation,
   dashboard, history, calculator, and share responses as **network-only**
   and serves a branded offline safety page when the network is
   unavailable: app shell styling, a plain statement that openpool needs a
   connection and that no dosing guidance is available offline, and
   **nothing else** — no cached readings, history, recommendations, or dose
   cards, no cached private data of any kind. Verified by an
   airplane-mode manual test recorded in the PR plus a check that no
   response containing chemistry data carries a cacheable service-worker
   route.
3. **Metric-mode honesty.** Until real metric support ships, the
   `unit_system` control in settings is disabled with visible text: "Metric
   display is not implemented yet — all inputs and results are US units."
   No stored preference may imply behavior that does not exist. Full metric
   conversion remains deferred (tracker Moved Later).

**Post-P scope.**

4. **Mobile add-reading flow (UI slice 2).** StepperInputs with
   `inputmode="decimal"`, "from last test" seeding with the visible tag,
   amber non-blocking "unusual — double-check?" hints wired to the soft
   bounds from Trustworthy Records, "More tests" disclosure, pinned save
   button, and the post-save results screen with recomputed status and
   recommendations (including the `retest` state from SP-1).
5. **History workflow (UI slice 4).** Segmented Readings/Additions/
   Maintenance control, date presets, mobile StackedRow cards vs desktop
   tables, row → edit, per-table export buttons. **UI slices 3 (calculator
   polish) and 5 (settings/share styling) remain deferred** — they are not
   scheduled by this plan.
6. **WCAG 2.2 AA audit.** Raise the documented target from 2.1 to 2.2 AA
   (note the change in `ui-design-plan.md` §8 and the tracker). Audit
   dashboard, add-reading, history, calculator, settings, login (once it
   exists) — including the 2.2 additions: 2.5.8 target size, 3.3.7
   redundant entry, 3.2.6 consistent help, 3.3.8 accessible authentication
   (coordinate with Locked Front Door). Fix findings; keep the
   icon+label-never-color-alone and chart-table-fallback rules.
7. **Offline snapshot decision (design note, not code).** Whether to offer
   a timestamped, read-only offline snapshot of the last-synced logbook is
   a separate design decision with its own privacy analysis — it reopens
   exactly the cached-private-data question SP-6 closes. It gets an
   explicit written decision before any implementation. No offline writes
   regardless.

**Acceptance criteria (Gate P scope).**

- Submitting any form with one bad field returns the form with every good
  field intact and the bad field flagged inline — verified by route tests.
- Airplane-mode test: every page yields the offline safety page; no
  reading, history row, recommendation, or dose value is visible offline;
  the page is branded and calm, not a browser error.
- The settings page makes exactly zero false claims.

**Dependencies.** Safe Dosing (the `retest` state must exist before the
post-P results screen renders it). Task 6's authentication criterion
coordinates with Locked Front Door.

**Non-goals.** Trends/charts (still gated on pilot history per the
tracker), offline write queue, theme work beyond fixing audit failures,
volume helper, target-profile settings UI.

---

### Milestone: Locked Front Door

**Problem.** There is no authentication; write APIs are open to any client
that can reach the service; the CSRF middleware trusts the `Host` header and
allows header-less writes; share tokens are plaintext at rest, echoed in the
settings form, and travel in query strings; there are no body-size limits,
no rate limits, no sessions. This is DeepSec items 1-2 plus the accepted
auth/session/CSRF/trusted-host/body/rate findings. Gate X blocks on all of
it; nothing here blocks Gate P (the pilot runs over loopback/tunnel/VPN).

The work is split into **three PR-sized slices** (review found the original
single slice unreviewable): (a) password/session core with fail-closed
bootstrap, (b) route-protection matrix, (c) bearer/API/share token work.
Request-hygiene middleware (CSRF/hosts/limits) is a fourth small slice.

**Affected files.**

- `openpool/security.py` (rewrite/extend), `openpool/main.py` (middleware
  wiring), `openpool/config.py` (new settings), `openpool/deps.py`
  (auth dependencies)
- `openpool/routers/api.py`, `openpool/routers/export.py`,
  `openpool/routers/pages.py` (route protection), new
  `openpool/routers/auth.py`
- `openpool/db.py` (hashed token storage, app-secret storage; a migration —
  the Trustworthy Records standing rule applies: same-slice `migrate.py`
  and parity updates)
- `openpool/services.py` — `share_access_allowed` (269-275)
- `openpool/templates/settings.html` (44: stop echoing the token),
  new `login.html`, `base.html` (logout affordance)
- `docs/deployment.md`, `docs/api.md`, `SECURITY.md`
- `tests/test_api.py`, new `tests/test_auth.py`

**Implementation tasks.**

1. **Slice A — password/session core with fail-closed bootstrap.** One
   password (this stays a single-user app — no `users` table, per the
   standing decision), stored as an scrypt hash (`hashlib.scrypt`, stdlib)
   in an `app_settings` table added by migration. Login page + signed
   session cookie (HMAC-SHA256 over an expiry payload, key from
   `OPENPOOL_SECRET` or a generated secret persisted under `/data`).
   **Bootstrap fails closed:** if no password is configured, the app serves
   only a locked page — the first-run setup form is available **only** when
   the request arrives on a loopback binding, or when the operator supplies
   an explicit one-time bootstrap secret via env
   (`OPENPOOL_BOOTSTRAP_TOKEN`) and presents it to the setup form. A
   non-loopback binding with no configured password and no bootstrap secret
   is locked, full stop — there is no window in which the first visitor
   names the password (Gate X threat T3). **Secure-cookie behavior is
   config-aware, not scheme-inferred:** an explicit
   `OPENPOOL_COOKIE_SECURE` setting (`auto|always|never`, default `auto`)
   where `auto` trusts forwarded-proto **only** from the configured trusted
   proxy, never blindly from the request scheme. `HttpOnly` and
   `SameSite=Lax` always.
2. **Slice B — route-protection matrix.** All pages except `/share/{id}`,
   the login/setup pages, the offline page, and static assets require a
   session. All `/api/*` write endpoints and the management reads
   (including **all exports** — threat T2) require a session or an API
   bearer token. `/api/health` and `/api/version` stay open. Share
   endpoints accept share credentials only and grant **only** the share
   snapshot — never exports, never writes. The matrix (route × principal ×
   expected status) is written down first, in the PR, and the test suite is
   generated from it.
3. **Slice C — token handling (DeepSec item 2).** API bearer tokens
   generated in settings, shown once, stored hashed (SHA-256 over the
   24-byte random value; `compare_digest` on check). Share tokens likewise
   hashed at rest via migration (existing plaintext tokens hashed in
   place — they keep working, they stop being readable); settings shows
   set/enabled state only, with explicit **rotate** and **disable**
   actions. **Gate X token policy (chosen):** in public mode, persistent
   query-string tokens are **disabled**; share links use
   `Authorization: Bearer` or a **one-time exchange** — the tokenized URL
   redeems once, sets a short-lived scoped cookie, and redirects to a
   token-free URL, so no persistent secret rides a query string or lands in
   logs as a reusable credential. Share responses carry
   `Cache-Control: no-store` and `Referrer-Policy: no-referrer` (threat
   T4). Pre-X private deployments may keep `?token=` for iframe/HA
   convenience with the leakage risk explicitly documented — the docs never
   claim tokens stay out of URLs or access logs while query tokens are on.
4. **Slice D — request hygiene.** Per-session CSRF token embedded in every
   form; verified on every page POST. Keep the origin/referer middleware as
   defense in depth but fix its policy: browser-shaped requests (session
   cookie present) with neither header are rejected; token-authed API
   requests are exempt (the bearer token is the CSRF defense there).
   Trusted hosts: `OPENPOOL_ALLOWED_HOSTS` (default `127.0.0.1,localhost`)
   enforced by middleware; the origin/referer comparison uses this
   allowlist, not the raw `Host` header. Body-size cap (default 1 MB).
   Fixed-window in-memory rate limits: aggressive on `/auth/login`
   (e.g. 5/minute/IP), modest on share endpoints, exports, and API writes
   (e.g. 60/minute/IP). **The in-memory limiter assumes a single process**
   (threat T5): startup refuses or loudly warns when configured with
   multiple workers, and `docs/deployment.md` pins the single-process
   deployment model.
5. **Calculator method (threat T1).** Switch the calculator form to POST
   with `Cache-Control: no-store` on the result page (or record an explicit
   accepted-risk entry for chemistry values in access logs); either way,
   assert by test that no credential or token can appear in a calculator
   URL.
6. **Docs.** `SECURITY.md`, `docs/api.md` (auth section), and
   `docs/deployment.md` updated; the "no public exposure" language flips to
   "public exposure requires Gate X" with the checklist; the written
   security review matrix template (routes × principals plus threats T1-T5)
   is added for the Gate X review.

**Acceptance criteria.**

- Unauthenticated requests: management pages redirect to login (or the
  locked page pre-bootstrap); API writes and exports return 401; share
  endpoints behave per the token policy; health/version open.
- A non-loopback binding with no configured password is locked — tested.
- No share or API token appears in any HTML response, API response, or
  export after initial generation. In public mode, no share or API token
  appears in a query string at all; in pre-X private mode, the query-token
  leakage risk is documented, not denied.
- CSRF: a forged cross-site POST with a valid session cookie but no token
  fails; all app forms still work.
- Rate limit, body cap, and the multi-worker refusal are observable via
  tests; legitimate flows unaffected.
- The route × principal matrix document and its generated tests agree with
  observed behavior — this artifact is the core of the Gate X review.

**Tests / verification.** `tests/test_auth.py` generated from the matrix;
bootstrap fail-closed test; CSRF, rate-limit, body-cap, token-rotation,
hashed-at-rest, one-time-exchange, and no-token-in-response tests; the full
existing suite passes with a logged-in test client fixture.

**Dependencies.** Trustworthy Records migrations scaffold (for
`app_settings` and token hashing). Slices land in order A → B → C → D.

**Non-goals.** Multi-user accounts, roles, OAuth/OIDC, TOTP, per-pool
permissions, HTTPS termination inside the container (the proxy owns TLS),
audit logging, shared-store rate limiting.

---

### Milestone: Sealed Supply Chain

**Problem.** D11 and the baseline: the lockfile is stale and vulnerable, the
image build ignores it, CI ignores it, actions are tag-pinned, the PR test
job holds `packages: write`, nothing scans dependencies or images — and the
accepted external audit evidence shows `main` unprotected and Dependabot
off. The published image being clean today is an accident of resolution
timing.

**Affected files.**

- `uv.lock`, `pyproject.toml` (only if refresh requires range bumps)
- `Dockerfile` (lines 1, 17-23), `.github/workflows/docker.yml`
- New `.github/dependabot.yml`
- `docs/deployment.md`, `docs/testing-plan.md`, `README.md` (Postgres CI
  status), `tests/test_postgres.py` (unchanged; CI wiring only)
- GitHub repository settings (manual, outside the repo — listed so it is
  not forgotten)

**Gate P scope — implementation tasks.**

1. **Lock refresh and least privilege.**
   - `uv lock --upgrade`; verify Starlette ≥ 1.3.1 and re-run the suite.
   - CI test job installs with `uv sync --locked --extra dev` so the lock is
     both used and verified on every PR.
   - Workflow permissions: top level `contents: read` only; the `build` job
     alone gets `packages: write`; `actions/checkout` sets
     `persist-credentials: false` in both jobs (DeepSec items 3-4).

**Gate X scope — implementation tasks.**

2. **Reproducible, pinned, scanned.**
   - Multi-stage `Dockerfile`: builder installs uv and runs
     `uv sync --locked --no-dev --extra postgres` from `uv.lock`; runtime
     stage copies the venv. Pin `python:3.13-slim` by digest.
   - Pin every third-party action to a full commit SHA (with the version as
     a comment).
   - Add CI steps: `uv lock --check` (lock matches pyproject), a dependency
     audit (`pip-audit` against the lock export or `uv`'s audit when
     available), and a Trivy scan of the built image that fails on
     high/critical before publish.
   - `.github/dependabot.yml` covering `pip` and `github-actions` weekly.
   - Manual repo settings: enable Dependabot alerts + security updates;
     branch protection on `main` (require PR, require the `test` check).
     Record completion in the tracker since it leaves no diff.
3. **PostgreSQL: CI or honesty.** Preferred: add a `postgres:16` service
   container to the CI test job and set `OPENPOOL_TEST_DATABASE_URL` so the
   2 skipped parity tests run on every PR. If that is rejected for cost or
   flakiness, instead label PostgreSQL **experimental — not CI-covered** in
   `README.md`, `docs/deployment.md`, and `docs/testing-plan.md`. One or the
   other; silent skipping ends here. (This task is Gate P: condition 8.)

**Acceptance criteria.**

- Gate P: the PR-triggered job runs with read-only token permissions
  (visible in the workflow run's token-permissions block) and installs from
  the refreshed lock; the suite is green.
- Gate X: two image builds from the same commit contain identical Python
  dependency versions (compare `pip freeze` from both); a deliberately
  vulnerable pin in a test branch fails CI before publish; PostgreSQL parity
  tests execute in CI (0 skipped) or every PostgreSQL mention carries the
  experimental label.

**Tests / verification.** CI runs on a branch demonstrating the green path,
the audit-failure path, and the permissions block. Local:
`docker compose up --build` and the GHCR compose path per the standing
container policy in `openpool-plan.md`.

**Dependencies.** None on other milestones; the Gate P slice lands early
because everything else rides through this pipeline.

**Non-goals.** SBOM publication, image signing/cosign, multi-arch builds,
Docker Hub, self-hosted runners. All fine later; none gate anything now.

---

### Milestone: Honest Paperwork

**Problem.** The documents disagree with the code and each other: the
tracker's "Read" list points at a nonexistent `AGENTS.md`; `README.md` still
says "planned shape"/"early implementation" while describing a feature-
complete Phase 3 app; `docs/api.md` predates the CRUD/maintenance/calculator
goals it should document; `plans/next-steps.md` interleaves a 2026-06-28
security section into a 2026-06-07 handoff; the live pilot checklist in
`docs/deployment.md` predates this plan and actively invites
recommendation-following that this plan blocks; and phase numbering means
something different in three documents. Stale docs are how the next chat
re-introduces a fixed defect.

**Affected files.** `README.md`, `docs/api.md`, `docs/deployment.md`,
`docs/review-notes.md`, `plans/project-tracker.md`, `plans/next-steps.md`,
`plans/openpool-plan.md` (phase-mapping note only), `plans/math-plan.md`
(borates status note), `plans/ui-design-plan.md` (WCAG target note),
`SECURITY.md`. Either create `AGENTS.md` or remove the reference.

**Implementation tasks.**

1. **Rewrite the pilot checklist (immediately — this is Gate P condition 7
   and its first half should land as the first slice of the build
   sequence).** The `docs/deployment.md` checklist is rewritten, not
   prepended to: recommendation-following is blocked until Gate P;
   pilot exposure is loopback/SSH-tunnel/private-VPN only; logging-only
   trusted-LAN use carries the open-writes risk statement; the backup steps
   point at the native backup and restore drill (not `all.json`); the
   "known not-yet-built" list matches this plan's deferrals.
2. Reconcile every roadmap/status claim with the working tree: the tracker
   is the single source of truth for status; other documents link to it
   instead of restating it.
3. Add a short mapping table (in the tracker) from the old phase numbers to
   this plan's named milestones, so historical references stay decodable.
4. `docs/api.md` regenerated to cover the actual route set in
   `openpool/routers/`, including the D6 breaking change and, once Locked
   Front Door lands, auth requirements per route.
5. Record the explicit deferrals with reasons: borates **dose calculation**
   (a v2 calculator behavior per `math-plan.md` §8; the v1 data-model half
   is done), metric conversion, offline write queue and the offline
   snapshot decision, trends/charts, multi-user, UI slices 3 and 5.
6. Fix the `next-steps.md` chronology (either date-stamped sections in
   order or fold the DeepSec items into this plan's milestones and say so).

**Acceptance criteria.** A new contributor reading `README.md` → tracker →
this plan gets zero contradictions; every "Read" pointer resolves; every
deferred plan item has a recorded reason; `git grep -n "AGENTS.md"` returns
only intentional references; the deployed pilot checklist contains no
instruction this plan forbids.

**Tests / verification.** Link check over the markdown set;
`git diff --check`; a human read-through, because doc coherence does not
unit-test.

**Dependencies.** Task 1 (checklist rewrite) lands **first**, before any
code slice — it encodes this plan's Decision. The final reconciliation pass
runs after the Gate P milestones merge (docs describe what shipped, not
what is hoped).

**Non-goals.** No new marketing copy, no license decision (still
deliberately open per `openpool-plan.md`), no publishing internal findings
that would map private deployment details.

---

## Recommended build sequence

Small, reviewable slices, each one PR-sized, each independently green, in
dependency order. Suitable for handing to visible coding agents one at a
time; none requires context beyond this plan plus the named files. Harm
fixes are front-loaded and, per review, **D3 and D1 land first** among the
chemistry fixes.

**Gate P slices:**

| # | Slice | Milestone | Size |
|---|-------|-----------|------|
| 1 | Rewrite `docs/deployment.md` pilot checklist + Decision/exposure language (SP-7) | Honest Paperwork (task 1) | S |
| 2 | SP-3 strength semantics in `normalize_percent` + caller/fixture updates + boundary tests (D3) | Safe Dosing | S |
| 3 | SP-1/SP-2 Fresh Reading Policy: constants, canonical chlorine set, `recommended_actions` evidence parameter, `build_snapshot` call graph, `retest` severity + tests (D1) | Safe Dosing | M |
| 4 | SP-5 dilution-zero refusal across chemistry/service/API/page + tests (D5) | Safe Dosing | S |
| 5 | SP-4 finite input/output guards: chemistry entrypoints, `Dose` serialization guard, `_parse_optional_float` + tests | Safe Dosing | S |
| 6 | D4 acid strength honored end-to-end (service, calculator select, dose-card label) + label-first warning | Safe Dosing | S |
| 7 | D2 CYA above-table refusal through targets/SLAM/recommendations + tests | Safe Dosing | M |
| 8 | Supply-chain P slice: `uv lock --upgrade`, `uv sync --locked` in CI, job-scoped permissions, `persist-credentials: false` | Sealed Supply Chain | S |
| 9 | Migrations scaffold (`schema_version`, ordered migrations, both backends) + `migrate.py`/export parity test harness | Trustworthy Records | M |
| 10 | Server-owned `tc`/`csi` (schema removal, always-compute) + API breaking-change note + parity tests | Trustworthy Records | S |
| 11 | `csi_meta_json` provenance column + UI/exports surfacing + same-slice `migrate.py`/export parity | Trustworthy Records | M |
| 12 | Cross-pool `linked_reading_id` enforcement (app-level both backends, constraint migration) + parity tests | Trustworthy Records | S |
| 13 | Validation bounds sweep (hard bounds, soft warnings, product-specific ranges) + edge tests | Trustworthy Records | M |
| 14 | Critical D1-D5 fixtures + corrected property tests (monotonicity, volume linearity, TA-effect signs) + derivations in `docs/formulas.md` | Verified Chemistry | M |
| 15 | Form error preservation across all page forms + route tests (D10) | Pilot Ergonomics | M |
| 16 | SP-6 offline safety page: network-only routes in `sw.js`, branded offline page, airplane-mode verification | Pilot Ergonomics | S |
| 17 | Metric-honesty settings change | Pilot Ergonomics | XS |
| 18 | Native backup: `openpool-backup` script + documented restore drill + `all.json` relabel | Recoverable Data | S |
| 19 | Postgres service in CI (or experimental labeling everywhere) | Sealed Supply Chain | S |
| 20 | Docs reconciliation P pass (tracker, README, `docs/api.md` breaking change, borates v2 note, `AGENTS.md`, next-steps chronology) | Honest Paperwork | M |
| 21 | **Gate P review**: walk the defect matrix and gate conditions; perform and record the restore drill; pilot may begin over loopback/tunnel/VPN | — | — |

**Post-P slices (ordered; none block the pilot):**

| # | Slice | Milestone | Size |
|---|-------|-----------|------|
| 22 | Staged-dose productization: `Dose` staging fields per contract + rendering + threshold tests | Safe Dosing (post-P) | M |
| 23 | Dose provenance columns (`calculation_json`/`expected_effects_json`) + log-this-dose carrier + same-slice `migrate.py`/export parity | Trustworthy Records (post-P) | M |
| 24 | Exhaustive fixture expansion for all remaining formulas + `docs/formulas.md` derivations | Verified Chemistry (post-P) | M |
| 25 | `all.json` versioning + restore endpoint with dry-run/conflict policy + round-trip tests | Recoverable Data (post-P) | M |
| 26 | CSV import for readings/additions + tests | Recoverable Data (post-P) | S |
| 27 | Mobile add-reading flow (UI slice 2) + screenshots | Pilot Ergonomics (post-P) | M |
| 28 | History workflow (UI slice 4) + screenshots (slices 3/5 stay deferred) | Pilot Ergonomics (post-P) | M |
| 29 | WCAG 2.2 AA audit + fixes (checklist artifact in the PR) | Pilot Ergonomics (post-P) | M |
| 30 | Offline snapshot design decision (written ADR, no code) | Pilot Ergonomics (post-P) | XS |

**Gate X slices:**

| # | Slice | Milestone | Size |
|---|-------|-----------|------|
| 31 | Auth slice A: password/session core + fail-closed bootstrap + config-aware secure cookies + tests | Locked Front Door | M |
| 32 | Auth slice B: route-protection matrix document + enforcement + generated auth-matrix tests (incl. exports, T2) | Locked Front Door | M |
| 33 | Auth slice C: hashed API/share tokens, rotate/disable UX, settings de-echo, one-time exchange, public-mode query-token disable (T4) | Locked Front Door | M |
| 34 | Auth slice D: CSRF tokens, fixed origin policy, trusted hosts, body cap, rate limits + single-worker guard (T5) | Locked Front Door | M |
| 35 | Calculator POST/no-store or recorded acceptance (T1) | Locked Front Door | S |
| 36 | Supply-chain X slice: locked multi-stage Dockerfile, digest/SHA pins, audit + Trivy CI gates, dependabot.yml, repo-settings checklist | Sealed Supply Chain | M |
| 37 | Proxy/auth deployment docs + completed written security review matrix (routes × principals + T1-T5) | Locked Front Door / Honest Paperwork | S |
| 38 | **Gate X review**: matrix walked and signed off; exposure decision | — | — |

After slice 8, the five ways the app can tell a user something dangerous are
closed and the pipeline is least-privilege, even if nothing else ever lands.

Standing rules for every slice (inherited from
`phase-3-chemistry-logbook-core.md`, extended here): formula docs and
fixtures before UI wiring; every write flow gets route tests; every export
gets a regression test; **every schema change updates `openpool/migrate.py`
and the exports in the same slice with the parity test extended**;
`uv run ruff check .`, `uv run pytest -q`, and `git diff --check` green; the
tracker updated when a slice lands.

## Definition of done

**Pilot-ready** means: a pool owner can log readings and follow the app's
dosing recommendations on one real pool — reached only via loopback, an SSH
tunnel, or a private VPN — and recover the database from a rehearsed native
backup; and every way the app previously could repeat, understate, misscale,
or fabricate a dose now refuses with an explanation, under a named safety
policy (SP-1 through SP-6), pinned by named regression tests. Concretely:
Gate P's eight conditions hold, the defect matrix has no open P rows, and
the rewritten pilot checklist in `docs/deployment.md` matches reality.

**Public-exposure-ready** means: everything above, plus nobody without the
operator's password or a deliberately issued token can read management data
or write anything; bootstrap fails closed; tokens are hashed, rotatable,
never re-displayed, and — in public mode — never persistent in a query
string; requests are host-checked, size-capped, and rate-limited under an
enforced single-process assumption; the image is a reproducible build of a
scanned, locked dependency set published by a least-privilege pipeline from
a protected branch; and the written security review matrix (every route ×
every principal, plus threats T1-T5) is complete with every row mitigated or
explicitly accepted. Concretely: Gate X's five conditions hold and the
defect matrix has no open rows at all.

Until then: log locally, dose from the label, and keep the port bound to
`127.0.0.1`.
