# openpool chemistry math plan

## Purpose

`openpool` needs its own transparent chemistry engine. The goal is not to clone proprietary app code. The goal is to implement pool-care calculations from first principles and public pool chemistry methodology, then validate the outputs against public references and known examples.

Every formula must have:

1. inputs
2. units
3. assumptions
4. source note
5. tests
6. validation fixtures

No mystery constants. If a constant exists, document where it comes from and lock it with tests.

## Clean implementation rule

Use public chemistry facts, public Trouble Free Pool methodology, public charts/articles, and independent hand calculations.

Do not:

- copy PoolMath app source code
- scrape private APIs
- reproduce proprietary UI/assets
- hide formulas in magic constants
- ship dosing formulas without tests

Public tables and public relationships can be encoded manually with source notes.

## Formula sourcebook format

Each formula should be documented in `docs/formulas.md` like this:

```yaml
name: liquid_chlorine_fc_raise
category: sanitizer
source_note: public pool chemistry / TFP-style method
inputs:
  pool_volume_gallons: gallons
  current_fc: ppm
  target_fc: ppm
  chlorine_percent: percent sodium hypochlorite
outputs:
  dose_gallons: gallons
  dose_fl_oz: fluid ounces
formula: dose_gallons = delta_fc * pool_volume_gallons / (10000 * chlorine_percent)
assumptions:
  - chlorine percent is product strength as labeled
  - pool is well mixed
validation:
  - 1 gallon of 10% chlorine raises FC by about 10 ppm in 10,000 gallons
  - compare against public pool calculators
```

## Implementation modules

```text
app/chemistry/
  units.py
  targets.py
  chlorine.py
  cya.py
  salt.py
  calcium.py
  alkalinity.py
  borates.py
  csi.py
  acid_base.py
  dosing.py
```

## v1 required math

### 1. Units and helpers

Functions:

- gallons ↔ liters
- ounces ↔ pounds
- fluid ounces ↔ gallons
- ppm mass conversions
- percent strength normalization
- safe rounding for display

Rules:

- Internal calculations use explicit units.
- API responses include unit labels.
- UI never displays unlabeled chemical amounts.

### 2. FC / chlorine

Required chemicals:

- liquid chlorine / sodium hypochlorite
- bleach
- cal-hypo later as side-effect chemical
- dichlor/trichlor later as side-effect chemicals

Core relationship:

```text
1 gallon of 10% liquid chlorine raises FC by about 10 ppm in 10,000 gallons.
```

Formula:

```text
dose_gallons = delta_fc_ppm * pool_gallons / (10000 * chlorine_percent)
dose_fl_oz = dose_gallons * 128
```

Outputs:

- gallons
- fluid ounces
- jugs if jug size is configured

Warnings:

- Do not calculate negative chlorine dose for lowering FC; suggest sunlight/time/water replacement instead.
- pH reading is unreliable when FC is high.

### 3. FC/CYA targets

Required target tables:

- liquid chlorine maintenance minimum/target
- SWG minimum/target
- SLAM/shock level
- optional mustard algae shock level later

Implementation:

- Encode public TFP-style CYA rows manually.
- Round CYA to supported chart buckets conservatively.
- For SLAM, never interpolate downward to an unsafe low target.

Example structure:

```python
FC_CYA_TABLE = {
    30: {"min": 2, "target_low": 4, "target_high": 6, "slam": 12},
    40: {"min": 3, "target_low": 5, "target_high": 7, "slam": 16},
}
```

### 4. CYA / stabilizer

Required chemicals:

- dry cyanuric acid / stabilizer
- dichlor/trichlor side effects later

Core relationship:

- CYA is tracked as ppm.
- Dry stabilizer dose is mass-based.
- The constant must be derived/documented and validated against public examples.

Outputs:

- ounces by weight
- pounds

Warnings:

- CYA dissolves slowly; do not retest/adjust too aggressively.
- During SLAM, avoid raising CYA to normal SWG maintenance targets unless intentionally exiting SLAM.

### 5. Salt

Formula:

```text
lbs_salt = delta_salt_ppm * pool_gallons * 8.34 / 1_000_000
```

Outputs:

- pounds
- 40-lb bags

Warnings:

- Salt should usually be raised slowly and retested.
- Salt readings vary by test/device; avoid chasing small deltas.

### 6. Calcium hardness

Required chemicals:

- calcium chloride
- calcium chloride dihydrate

Plan:

- Use ppm mass math adjusted for chemical purity/form.
- Store product-specific active fraction constants.
- Validate against public calculators.

Outputs:

- ounces by weight
- pounds

Warnings:

- High CH increases CSI scaling risk.
- Calcium additions are not easily reversible except dilution/water replacement.

### 7. Total alkalinity

TA is required for v1.

Required operations:

- calculate dose to raise TA using sodium bicarbonate / baking soda
- log TA readings
- include TA in CSI inputs
- include TA in pH/acid warning context
- support target ranges by pool mode/type

Core relationship:

- TA is measured as ppm as CaCO3.
- Baking soda raises TA with relatively small pH effect.
- Soda ash raises pH and also raises TA, but should be handled under pH/acid-base side effects.

Implementation plan:

```python
def dose_baking_soda_for_ta(
    pool_gallons: float,
    current_ta: float,
    target_ta: float,
    product_purity: float = 1.0,
) -> Dose:
    ...
```

Formula strategy:

- Derive from ppm as CaCO3 equivalent and sodium bicarbonate molar/equivalent mass.
- Validate against public calculator examples.
- Store constant in `alkalinity.py` with source note.

Known practical rule to validate:

```text
Baking soda raises TA; output should be in pounds/ounces by weight.
```

Warnings:

- Do not recommend lowering TA as a single chemical dose.
- Lowering TA is a process: acid lowers pH/TA, aeration raises pH with less TA rise, repeat.
- pH and TA are coupled; acid additions should show expected TA side effect once acid-base math exists.
- TA target depends on chlorination method, fill water, pH drift, and CSI.

### 8. Borates

Borates are required for v1 data model and v2 calculator behavior.

Required v1 support:

- store borates reading in ppm
- chart borates history
- export borates in CSV/JSON/share endpoint
- include borates in CSI/pH buffering context where formula supports it
- calculate borate raise dose if formula is validated

Required chemicals:

- boric acid
- borax / sodium tetraborate decahydrate
- muriatic acid side-dose when using borax, if implemented

Implementation plan:

```python
def dose_boric_acid_for_borates(
    pool_gallons: float,
    current_borates: float,
    target_borates: float,
    product_purity: float = 1.0,
) -> Dose:
    ...

def dose_borax_for_borates(...):
    ...
```

Formula strategy:

- Treat borates as ppm boron/borate according to public pool calculator convention; document exact convention before shipping.
- Derive product dose from chemical composition and validate against public calculators.
- Prefer boric acid recommendation first because it has cleaner pH behavior than borax.
- If recommending borax, include required acid compensation only after acid-base math is validated.

Warnings:

- Borates are optional; do not suggest them as required chemistry.
- Avoid borates where pet ingestion risk matters.
- Borate changes are not easy to reverse except dilution.
- Borax raises pH significantly and needs acid compensation.

## v2 required math

### 9. CSI

Inputs:

- pH
- water temperature
- calcium hardness
- total alkalinity
- CYA
- salt/TDS approximation
- borates if supported by alkalinity correction model

Plan:

- Implement CSI from public formula references.
- Correct carbonate alkalinity from TA by accounting for CYA contribution and optionally borates.
- Validate against public calculators and known examples.

Warnings:

- CSI is especially important for plaster/pebble pools.
- High pH, high CH, high TA, high temperature, and high salt tend to push CSI upward.
- Low pH, low CH, low TA, and cold water tend to push CSI downward.

### 10. Acid/base and pH

Required operations:

- muriatic acid to lower pH
- soda ash/borax to raise pH later
- TA side effect estimates

Plan:

- Implement only after FC/CYA/salt/CH/TA basics pass tests.
- Mark output approximate.
- Include warnings when FC is high, borates are present, or TA is unusual.

## v3 optional math

- SWG runtime/percentage estimate
- OCLT helper
- dilution/refill model
- trichlor puck planner
- cost tracking
- chemical inventory depletion
- multi-body pool/spa mode calculations

## Test plan

Required test files:

```text
tests/test_units.py
tests/test_chlorine.py
tests/test_targets.py
tests/test_cya.py
tests/test_salt.py
tests/test_calcium.py
tests/test_alkalinity.py
tests/test_borates.py
tests/test_csi.py
```

Required fixture file:

```text
tests/fixtures/public_reference_cases.json
```

Fixture shape:

```json
{
  "case_id": "liquid_chlorine_10000gal_10pct_delta1",
  "inputs": {
    "pool_gallons": 10000,
    "current_fc": 4,
    "target_fc": 5,
    "chlorine_percent": 10
  },
  "expected": {
    "dose_gallons": 0.1,
    "dose_fl_oz": 12.8
  },
  "tolerance_percent": 2,
  "source_note": "Public pool chemistry identity: 1 gallon of 10% liquid chlorine raises 10,000 gallons by about 10 ppm."
}
```

## First implementation order

Build in this exact order:

1. units
2. chlorine
3. FC/CYA targets
4. CYA
5. salt
6. calcium hardness
7. total alkalinity / baking soda
8. borates storage/export
9. boric acid dose
10. CSI
11. acid/base pH dosing
12. borax + acid compensation

Why this order:

- FC/CYA/salt/CH/TA are mostly mass/ppm math.
- Borates need storage early because users track them historically.
- CSI needs TA and borate correction decisions.
- Acid/base math is where calculators become lying slot machines if rushed.

## Acceptance criteria

- Every formula has docs.
- Every formula has tests.
- Every dose output includes units.
- Every approximate formula says it is approximate.
- Total alkalinity and borates are first-class readings, exports, and chart fields.
- No app code copied from proprietary calculators.
