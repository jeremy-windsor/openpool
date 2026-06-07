# openpool UI / design plan

This is the design companion to [`openpool-plan.md`](openpool-plan.md) and
[`math-plan.md`](math-plan.md). Those plans answer *what the app stores and
calculates*. This plan answers *what it looks like, how it feels in the hand,
and how a tired pool owner actually uses it standing next to the water in the
sun*.

The backend plan picks a server-rendered stack (FastAPI + Jinja2 + HTMX/Alpine
+ Chart.js). This design plan is written to that stack: every pattern here is
achievable with HTML, CSS, a little progressive-enhancement JS, and a service
worker. No SPA framework required.

---

## 1. Who is at the keyboard

One primary persona drives every decision:

> **The owner, poolside, on a phone.** One hand free. Wet fingers. Bright
> midday sun washing out the screen. Wants to punch in a test result and be
> told, in plain language, what to add and how much — in under 30 seconds.

Secondary contexts the same UI must still serve gracefully:

- **The owner at a desk** reviewing trends on a wide screen.
- **A guest / house-sitter** following instructions without understanding pool
  chemistry.
- **A read-only viewer** looking at the share page or a Home Assistant card.

Design for the poolside phone first. Everything else is the same UI given more
room.

---

## 2. Design principles

1. **Glanceable over comprehensive.** The dashboard answers "is my pool OK and
   what do I do next" before it shows a single number.
2. **One primary action per screen.** There is always one obvious, large,
   thumb-reachable thing to do. Secondary actions get out of the way.
3. **Plain language first, chemistry second.** "Add 32 oz of liquid chlorine"
   is the headline. The ppm math is available but never required to act.
4. **Show the work, on demand.** Every recommendation can be expanded to reveal
   inputs, formula, assumptions, and confidence. Trust is the moat (per the
   math plan's "no mystery constants" rule).
5. **Never alarm without a remedy.** A red status always pairs with a concrete
   next step. No dead-end warnings.
6. **Sunlight and wet hands are the test environment.** High contrast, large
   targets, forgiving inputs. If it fails at noon by the pool, it failed.
7. **Honest about uncertainty.** Approximate results (pH, TA, CSI) are visually
   marked as approximate. The UI never fakes precision the chemistry lacks.
8. **Local-first, works offline.** The phone may have no signal at the pool.
   The app loads and accepts a reading without a network round-trip.

---

## 3. Visual language

### 3.1 Color system

Color is **semantic and status-driven**, not decorative. The palette is built
around a calm water-blue brand with a hard-working traffic-light status set.

```text
Brand
  --brand-900  deep pool blue   (headers, primary buttons)
  --brand-600  pool blue        (links, active states)
  --brand-100  pale water       (selected backgrounds)

Status (the workhorses)
  --good       balanced green   "in range"
  --caution    amber            "drifting / act soon"
  --danger     red              "out of range / act now"
  --info       neutral blue     "informational / approximate"

Surface (light)            Surface (dark)
  --bg        near-white         near-black slate
  --surface   white              elevated slate
  --border    cool gray          muted slate
  --text      ink                off-white
  --text-dim  slate gray         muted gray
```

**Rules**

- Status color is **never the only signal.** Every status also carries an icon
  and a text label (color-blind safety, WCAG 1.4.1). Green check, amber
  triangle, red octagon.
- Contrast meets **WCAG AA** minimum (4.5:1 body text, 3:1 large text/UI).
  Status colors are chosen at their accessible shades, not their pretty ones.
- A reading value is colored by *its own range*, not the overall pool status,
  so a single bad number stands out in a sea of green.

### 3.2 Three themes

The theme toggle offers three modes, not two — outdoor readability earns its
own mode:

| Mode | When | Characteristics |
|------|------|-----------------|
| **Light** | Default / indoors | White surfaces, soft shadows. |
| **Dark** | Evening / OLED | Slate surfaces, dimmed status colors. |
| **Outdoor (high-contrast)** | Bright sun | Max contrast, heavier weights, larger type, flatter colors, no subtle grays. |

Default to **system preference** (`prefers-color-scheme`), with a manual
override persisted in settings. Respect `prefers-reduced-motion` for all
transitions and chart animations.

### 3.3 Typography

- **System font stack** (no web-font download — faster, offline-safe):
  `-apple-system, "Segoe UI", Roboto, sans-serif`.
- **Tabular / lining numerals** (`font-variant-numeric: tabular-nums`) for every
  reading, dose, and chart axis so digits align in tables and don't jump.
- Type scale (mobile baseline, fluid up to desktop):

  ```text
  Display  reading hero numbers      ~40px / bold
  H1       page title                ~24px
  H2       card / section title      ~18px
  Body     default                   16px   (never below 16px — iOS zoom)
  Caption  units, timestamps, hints  13px
  ```

- Body text **never below 16px** on inputs (prevents iOS auto-zoom on focus).

### 3.4 Spacing, shape, touch targets

- 8px spacing grid. Card padding 16px, section gaps 24px.
- Minimum touch target **48×48px** (WCAG 2.5.5 / mobile reality). Steppers,
  toggles, nav items all clear this.
- Rounded cards (12px) and pills (full). Generous whitespace = calm.
- One elevation level for cards; reserve stronger shadow for sheets/modals only.

### 3.5 Iconography

A small, consistent line-icon set (one library, e.g. Lucide) for: dashboard,
add/test, history/chart, calculator, settings, chemical drop, warning triangle,
check, clock (last-test age), share, export. Icons always pair with a text
label in navigation.

---

## 4. Information architecture & navigation

```text
┌─────────────────────────────────────┐
│  Pool name ▾        ☀/🌙   ⚙        │  top bar (pool switcher + theme + settings)
├─────────────────────────────────────┤
│                                     │
│            page content             │
│                                     │
├─────────────────────────────────────┤
│  🏠        📋        ＋       📈   🧪 │  bottom nav (thumb zone)
│ Home    History   ADD   Trends Calc │
└─────────────────────────────────────┘
```

- **Bottom tab bar on mobile** — thumb-reachable, fixed. Five destinations:
  Home (dashboard), History, **Add reading (center, raised primary)**, Trends,
  Calculator. Settings lives in the top bar (less frequent).
- **Center "Add" button is the app's heartbeat** — raised, brand-colored, the
  single most-used action. It opens the new-reading flow.
- **Pool switcher** is the top-left title as a dropdown (the data model already
  supports multiple pools/spa — the UI must too, even if most users have one).
  With a single pool, it renders as a plain title, no dropdown chrome.
- **Desktop / tablet**: the bottom bar becomes a **left sidebar**; content gets
  a max-width reading column plus room for side-by-side charts. Same IA, more
  room — no separate desktop design.

URL ↔ destination map (matches backend page routes):

```text
/              Home / dashboard
/readings/new  Add reading
/history       History tables
/trends        Charts            (split out from /history for clarity)
/calculator    Calculator
/settings      Settings
/share/{id}    Read-only share (no app chrome)
```

---

## 5. Page-by-page UX

Each page is specified as: **purpose → layout → key interactions → states.**

### 5.1 Home / Dashboard `/`

**Purpose:** answer "is my pool OK, and what do I do next" in one glance.

**Layout (top to bottom):**

1. **Overall status banner.** One line, color + icon + words:
   "Balanced — no action needed" / "Add chlorine today" / "Act now: low FC".
   This is computed from the readings vs. targets, and it's the first thing the
   eye lands on.
2. **Last-test age chip.** "Tested 2 days ago" — turns amber/red as the reading
   ages past the pool's expected test cadence. Stale data is itself a warning.
3. **Recommended actions list.** Zero-to-few cards: each is a plain-language
   instruction ("Add ~32 oz liquid chlorine") with a **"Log this addition"**
   button and an expandable "why / show math" disclosure.
4. **Reading tiles grid.** FC, CC, pH, TA, CH, CYA, salt, CSI, water temp. Each
   tile: label, big tabular number, unit, and a colored range bar showing where
   the value sits inside its target band. Tap a tile → its trend chart.
5. **Recent additions** mini-list (last 3) and a link to history.

**Interactions:** "Log this addition" pre-fills the addition form from the
recommendation. Pull-to-refresh re-fetches latest.

**States:**
- *First run / no readings:* friendly empty state with a single big "Add your
  first reading" CTA and a one-line explainer. No fake zeros.
- *Stale (no recent reading):* banner nudges a fresh test.
- *Offline:* a subtle "offline — showing last synced data" ribbon; data still
  renders from cache.

### 5.2 Add reading `/readings/new`

This is the **most-used, most-optimized screen.** Speed and forgiveness win.

**Layout:**

- Fields ordered by how often they're tested, **common first**:
  - Always visible: **FC, CC, pH** (the daily/most-frequent trio).
  - Collapsed "More tests" section: TA, CH, CYA, salt, borates, water temp,
    filter pressure. Remembered open/closed per user.
- Each numeric field is a **large stepper input**: big `−` / value / `+` with a
  tap-to-type number pad (`inputmode="decimal"`). Wet-finger friendly; no tiny
  spinner arrows.
- Inputs are **pre-seeded with the last reading's values** (most readings move a
  little, not a lot) — but clearly marked as "from last test" so the user
  confirms rather than blindly saves.
- **Inline validation, not blocking:** out-of-plausible-range entries (e.g. pH
  9.5, FC 50) get a gentle amber "unusual — double-check?" hint, never a hard
  stop. Real life produces weird readings; don't fight the user.
- **Test timestamp** defaults to now, editable (you sometimes log a test from
  earlier). Stored UTC, shown in the pool's local timezone.
- Notes field (free text) at the bottom.

**Primary action:** a single full-width **"Save reading"** button pinned to the
bottom (above the nav), always reachable by thumb.

**After save (the payoff):** transition straight to a **results screen**:
- "Saved." confirmation toast.
- Recomputed status + the recommended actions for *this* reading.
- One-tap **"Log the chemicals you added"** shortcut.

**States:** saving (optimistic, button shows spinner), offline (queued — see
§9), validation hints inline.

### 5.3 Calculator `/calculator`

**Purpose:** "I want to change X to Y — how much do I add?" without logging a
full test.

**Layout:**

- Pick a **goal** first (chips): Raise FC, Lower pH, Raise TA, Raise CH, Raise
  CYA, Raise salt, Raise borates. The chosen goal reveals only the relevant
  inputs — don't show a wall of every field.
- Inputs: current value, target value, pool volume (pre-filled from settings),
  product type & strength (pre-filled from settings defaults, overridable).
- **Result card** is the hero: the dose in the most useful unit (oz / lbs /
  gallons / **jugs or bags** when configured — "≈ 1.5 jugs"), plus secondary
  units underneath.
- **Side-effects panel:** if the chosen chemical moves other parameters (trichlor
  → FC+CYA+pH, cal-hypo → FC+CH, acid → pH+TA), show those as small "this will
  also..." notes. This is a differentiator and a safety feature.
- **Confidence ribbon:** exact-ish math (FC/salt/CH/CYA) shows nothing special;
  approximate math (pH/TA/CSI-driven) shows a clear "approximate — verify by
  retesting" badge per the math plan.
- "Show the math" disclosure: inputs → formula → assumptions → source note.

**Interactions:** changing any input live-updates the result (HTMX/Alpine). A
"Log this as an addition" button carries the result into the additions log.

### 5.4 History `/history`

**Purpose:** the ledger. Tabular truth.

**Layout:** segmented control to switch among **Readings / Additions /
Maintenance** tables. Date-range filter (presets: 7d, 30d, 90d, all + custom).
Each table is sortable, with sticky header. Tap a row → detail/edit sheet.
Per-table **Export CSV** and overall **Export JSON backup** buttons live here.

**Mobile table strategy:** narrow screens collapse each row into a **stacked
card** (date + key values) rather than a horizontally-scrolling spreadsheet.
Wide screens get the real table.

**States:** empty (per tab), filtered-to-empty ("no readings in this range").

### 5.5 Trends `/trends`

**Purpose:** see drift over time; catch problems before they're red.

**Layout:** a stack of focused line charts (FC, pH, TA, CH, CYA, salt, CSI,
water temp). Each chart:

- Shows the **target band as a shaded zone** behind the line — instantly reveals
  in-range vs. out-of-range history without reading numbers.
- Markers for **chemical additions** plotted on the timeline, so you can see "I
  added acid here → pH dropped there." This cause/effect view is the reason
  trends matter.
- Shared date-range control across all charts.
- Tap a point → that reading's detail.

**States:** "need at least 2 readings to chart a trend" empty state.

**Accessibility:** every chart has an accessible text/table fallback and is not
the *only* way to read the data (the History tables are).

### 5.6 Settings `/settings`

Grouped sections:

- **Pool profile:** name, volume, spa volume, surface type, sanitizer type.
  Volume can be entered directly or via a **volume helper** (shape + dimensions
  → gallons/liters) since most owners don't know their exact volume.
- **Targets:** choose a target mode/profile (Maintenance, SLAM/shock, Spa) and
  view/edit the target ranges. Changes are logged to `pool_settings_history`.
- **Products & defaults:** default chlorine strength, acid strength, stabilizer
  type, **jug size and bag size** (so doses can read as "1.5 jugs").
- **Units:** **gallons/pounds/°F ↔ liters/kilograms/°C** global toggle. This is
  first-class, not an afterthought — half the world is metric (see plan gap
  note). All inputs, results, charts, and exports honor it.
- **Appearance:** theme (Light / Dark / Outdoor / System).
- **Sharing:** enable read-only share, generate/rotate token, copy share URL,
  toggle "include notes in share" (off by default).
- **Data:** export all (JSON), import CSV, and the backup story.
- **Integrations (advanced, collapsed):** Home Assistant URL hint, MQTT,
  nodejs-poolController state URL.

### 5.7 Share page `/share/{id}`

**Purpose:** a clean, **chrome-free, read-only** status page for a link or an
embedded iframe. No bottom nav, no edit affordances.

**Layout:** pool name, overall status banner, the reading tiles grid, last-test
age, and (only if explicitly enabled) recommendations. Never shows private
notes unless the owner opted in. Looks good embedded in a Home Assistant
dashboard card.

---

## 6. Component library (design system)

A small set of reusable, server-renderable components. Build these once; every
page composes them.

| Component | Purpose / notes |
|-----------|-----------------|
| **StatusBanner** | Full-width color+icon+text verdict. The dashboard's headline. |
| **ReadingTile** | Label, big tabular value, unit, range bar. The atom of the dashboard. |
| **RangeBar** | Horizontal bar showing a value's position inside its target band; colored by status. |
| **RecommendationCard** | Plain-language action + "Log it" button + "show math" disclosure. |
| **DoseResultCard** | Hero dose value, multi-unit, jugs/bags, side-effects, confidence ribbon. |
| **StepperInput** | Large −/value/+ numeric input, decimal keypad, optional unit suffix. |
| **Chip / SegmentedControl** | Goal pickers, table switchers, date presets. |
| **TrendChart** | Line chart + target band + addition markers + text fallback. |
| **DataTable / StackedRow** | Responsive table that collapses to cards on mobile. |
| **Toast** | Transient confirmation ("Saved", "Logged 32 oz chlorine"). |
| **Disclosure** | "Show the math / why" expandable, used everywhere for transparency. |
| **ConfidenceBadge** | "Approximate — verify by retesting" marker. |
| **EmptyState** | Icon + one line + single CTA. Used on every list/chart at zero data. |
| **BottomNav / Sidebar** | The responsive primary navigation. |
| **Sheet / Modal** | Edit a reading, confirm a destructive action. |

Document these in `docs/ui-components.md` with the markup contract so the other
models building the code stay consistent.

---

## 7. Interaction patterns & UI states

For **every** data view, design four states explicitly — not just the happy path:

1. **Empty** — first-run or no data in range. Friendly, one CTA, no fake zeros.
2. **Loading** — skeleton placeholders (not spinners) for content; spinners only
   on action buttons.
3. **Error** — plain-language message + retry. Never a raw stack trace or
   silent failure.
4. **Success / populated** — the real content.

Plus cross-cutting interaction rules:

- **Optimistic UI on save** — the reading appears instantly; reconcile on
  server confirm. Poolside latency shouldn't block the next tap.
- **Confirmation for destructive actions only** (delete reading/addition).
  Everything else is undoable via edit; don't nag.
- **Toasts for confirmations**, inline hints for validation, banners for
  persistent state (offline, stale). Don't mix these up.
- **Reduced motion** honored throughout.

---

## 8. Accessibility (WCAG 2.1 AA target)

Not a phase-5 bolt-on — baked into the component contracts:

- **Color is never the sole signal** — icon + label accompany every status.
- **Contrast AA** for text and UI; Outdoor mode exceeds it.
- **Touch targets ≥ 48px**, adequate spacing between them.
- **Full keyboard operability** and visible focus rings (desktop users, switch
  access).
- **Semantic HTML + ARIA** where needed; forms have real `<label>`s, inputs use
  correct `inputmode`/`type`.
- **Charts have text/table equivalents** — never the only path to the data.
- **Screen-reader sanity pass** on the add-reading flow and dashboard at
  minimum.
- Respect `prefers-reduced-motion` and `prefers-color-scheme`.

---

## 9. Offline & PWA (poolside reality)

The pool is often the spot with the worst Wi-Fi. The app must work there.

- **Installable PWA**: web app manifest (name, icons, theme color, standalone
  display) so it lives on the home screen like a native app.
- **Service worker**: app shell (HTML/CSS/JS) cached for instant, offline load.
- **Offline reads**: last-known dashboard/readings render from cache with an
  "offline — last synced X ago" ribbon.
- **Offline writes (queue)**: a reading or addition entered offline is stored
  locally and **synced when connectivity returns**, with a clear "pending sync"
  badge. The user must never lose a poolside entry to a dropped signal.
- This complements (does not replace) the SQLite source of truth — the queue is
  a transport buffer, the server DB remains canonical.

> Scope note: full offline-write sync is a **Phase 4–5** enhancement. Phase 0–3
> ship installable + offline-read; offline-write queue follows once the data
> flow is stable.

---

## 10. Microcopy & tone

- **Calm, plain, imperative.** "Add 32 oz of liquid chlorine." Not "Sodium
  hypochlorite deficiency detected."
- **Numbers carry units, always.** No bare "32" — it's "32 oz" or "≈1.5 jugs".
- **Honesty in uncertainty.** "Approximate — retest to confirm." Never imply
  precision the chemistry doesn't have.
- **Encouraging at empty states.** "No readings yet — let's log your first test."
- **Safety reminders where they matter** (acid handling, never mixing
  chemicals) as quiet helper text, not nags.

---

## 11. Responsive strategy

Mobile-first, three breakpoints, **same IA throughout**:

```text
≤ 600px   Phone    Bottom tab bar. Single column. Stacked table rows.
600–1024  Tablet   Bottom bar OR sidebar. Two-column dashboard. Real tables.
≥ 1024px  Desktop  Left sidebar. Max-width content column + side charts.
```

No separate desktop app — the phone layout *expands* into the larger screens.
Charts and tables get more room; navigation relocates; nothing is redesigned.

---

## 12. Design ↔ build phasing

Maps onto the build phases in `openpool-plan.md`:

| Build phase | Design deliverables |
|-------------|--------------------|
| **0 — skeleton** | Design tokens (color/type/space CSS variables), base layout, bottom nav/sidebar shell, theme switch, a11y baseline. |
| **1 — logbook** | StepperInput, add-reading flow, History tables + stacked rows, EmptyState, Toast, basic ReadingTile. |
| **2 — math MVP** | Calculator page, DoseResultCard, ConfidenceBadge, side-effects panel, "show the math" Disclosure. |
| **3 — dashboard** | StatusBanner, ReadingTile + RangeBar polish, RecommendationCard, last-test-age chip, TrendChart with target bands + addition markers, Outdoor mode. |
| **4 — integrations** | Chrome-free Share page, HA-embeddable card styling, PWA manifest + offline-read. |
| **5 — hardening** | Offline-write queue, import UI, screen-reader pass, reduced-motion polish, settings depth (units, sharing, products). |

---

## 13. Design tooling & artifacts

- **CSS custom properties** as the single source of design tokens
  (`static/tokens.css`) — colors, spacing, type, radii, themes. Every component
  reads from these; theming is just swapping variable sets.
- **Component contracts** documented in `docs/ui-components.md` so collaborating
  models produce consistent markup.
- **No heavy design tool dependency required** — but if hi-fi mockups are made
  (Figma/Excalidraw), keep them out of the repo or in a `/design` folder that's
  fine to publish (no private pool data, ever).
- Keep the rendered HTML semantic enough that the "design system" is mostly CSS
  + a handful of Jinja macros, not a JS component runtime.

---

## 14. Open design questions (decide before/at Phase 0)

1. **Icon set** — Lucide vs. inline custom SVGs (favor inline for offline/no
   dependency).
2. **Chart library** — Chart.js (named in plan) is fine; confirm it can render
   the target-band shading + addition markers cleanly, else consider a
   lightweight SVG approach.
3. **Multi-pool prominence** — ship the pool switcher in the top bar from day
   one (data model supports it), or hide until a 2nd pool exists? Recommend:
   build it, render-as-title when there's one pool.
4. **Volume helper depth** — simple shapes (rect/round/oval) in v1; irregular
   shapes later.
5. **Metric default** — detect from locale, or default imperial with easy
   toggle? Recommend locale-detect with override.
