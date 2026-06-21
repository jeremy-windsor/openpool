# Formula Notes

Every formula in `openpool` has explicit inputs, units, assumptions, and tests.
The app owns these calculations; it does not copy proprietary calculator code.

## Liquid Chlorine FC Raise

```yaml
name: liquid_chlorine_fc_raise
category: sanitizer
source_note: public pool chemistry identity
inputs:
  pool_gallons: gallons
  current_fc: ppm
  target_fc: ppm
  chlorine_percent: percent sodium hypochlorite, e.g. 10 for 10%
outputs:
  dose_fl_oz: fluid ounces
  dose_gallons: gallons
formula: dose_gallons = delta_fc * pool_gallons / (10000 * chlorine_percent)
assumptions:
  - 1 gallon of 10% liquid chlorine raises FC by about 10 ppm in 10,000 gallons
  - pool is well mixed
validation:
  - 10,000 gallons, FC 4 -> 5, 10% chlorine = 0.1 gal = 12.8 fl oz
```

## Dry Stabilizer CYA Raise

```yaml
name: dry_stabilizer_cya_raise
category: stabilizer
source_note: ppm mass conversion
inputs:
  pool_gallons: gallons
  current_cya: ppm
  target_cya: ppm
  product_purity: fraction, 1.0 default
outputs:
  dose_oz_weight: ounces by weight
  dose_lbs: pounds
formula: product_lbs = delta_cya * pool_gallons * 8.345404452 / 1000000 / product_purity
assumptions:
  - CYA ppm is treated as ppm by mass in pool water
  - dry stabilizer is near pure cyanuric acid unless configured otherwise
validation:
  - 10 ppm in 10,000 gallons = about 13.35 oz by weight of pure product
```

## Salt Raise

```yaml
name: salt_raise
category: salt
source_note: ppm mass conversion
inputs:
  pool_gallons: gallons
  current_salt: ppm
  target_salt: ppm
outputs:
  dose_lbs: pounds
formula: lbs_salt = delta_salt_ppm * pool_gallons * 8.345404452 / 1000000
assumptions:
  - salt test is close enough for practical dosing
validation:
  - 1,000 ppm in 10,000 gallons = about 83.45 lb salt
```

## Calcium Hardness Raise

```yaml
name: calcium_chloride_ch_raise
category: hardness
source_note: stoichiometric ppm mass conversion
inputs:
  pool_gallons: gallons
  current_ch: ppm as CaCO3
  target_ch: ppm as CaCO3
  product: calcium_chloride (110.98 g/mol) or calcium_chloride_dihydrate (147.01 g/mol)
outputs:
  dose_oz_weight: ounces by weight
  dose_lbs: pounds
formula: product_lbs = delta_ch * pool_gallons * 8.345404452 / 1000000 * (product_molar_mass / 100.09)
assumptions:
  - CH is measured as ppm CaCO3 (100.09 g/mol)
  - product is 100% of the labeled compound; retail "hardness increaser" is usually the dihydrate
validation:
  - 10 ppm in 10,000 gallons, dihydrate = about 1.23 lb (19.6 oz)
  - 10 ppm in 10,000 gallons, anhydrous = about 0.93 lb (14.8 oz)
```

## Total Alkalinity Raise

```yaml
name: baking_soda_ta_raise
category: alkalinity
source_note: stoichiometric ppm mass conversion
inputs:
  pool_gallons: gallons
  current_ta: ppm as CaCO3
  target_ta: ppm as CaCO3
outputs:
  dose_oz_weight: ounces by weight
  dose_lbs: pounds
formula: product_lbs = delta_ta * pool_gallons * 8.345404452 / 1000000 * (2 * 84.006 / 100.09)
assumptions:
  - TA is measured as ppm CaCO3 (2 equivalents per mole)
  - sodium bicarbonate (84.006 g/mol) provides 1 equivalent per mole
  - baking soda is pure sodium bicarbonate
validation:
  - 10 ppm in 10,000 gallons = about 1.4 lb (22.4 oz) baking soda
```

## CSI (Calcite Saturation Index)

CSI is computed automatically when a reading has pH, TA, and CH, and is
recomputed whenever a reading is edited. It is stored on the reading and shown
on the dashboard as an approximate scale/corrosion signal.

```yaml
name: csi
category: balance
source_note: Langelier-style saturation index with pool corrections
inputs:
  ph: required
  ta: ppm as CaCO3, required
  ch: ppm as CaCO3, required
  cya: ppm, optional (cyanurate alkalinity correction, 0.33 * CYA)
  water_temp_f: optional, defaults to 80 F with a warning
  salt: ppm, optional TDS stand-in, defaults to 1000 ppm with a warning
  borates: ppm, optional (ionized fraction subtracted using pKa 9.2)
formula: |
  carbonate_alk = ta - 0.33 * cya - borates / (1 + 10^(9.2 - ph))
  pHs = 9.3 + (log10(TDS) - 1) / 10
        + (-13.12 * log10(temp_C + 273) + 34.55)
        - (log10(ch) - 0.4) - log10(carbonate_alk)
  csi = ph - pHs
assumptions:
  - the cyanurate correction factor 0.33 is an approximation near pH 7.5
  - this is a trend signal, not a lab measurement; +/-0.3 is treated as balanced
validation:
  - pH 7.5, TA 70, CH 350, CYA 40, 80 F, salt 3000 = about -0.21
```

## Dry Chlorine FC Raise (trichlor, dichlor, cal-hypo)

These products change more than FC, so the dose result includes expected side
effects from the same stoichiometry.

```yaml
name: dry_chlorine_fc_raise
category: sanitizer
source_note: stoichiometric available-chlorine mass conversion
inputs:
  pool_gallons: gallons
  current_fc: ppm as Cl2
  target_fc: ppm as Cl2
  product: trichlor | dichlor | cal_hypo
  available_chlorine_percent: cal-hypo label strength only, default 65
outputs:
  dose_oz_weight: ounces by weight
  dose_lbs: pounds
  effects: expected ppm side effects
formula: product_lbs = delta_fc * pool_gallons * 8.345404452 / 1000000 / available_chlorine
constants:
  trichlor_available_chlorine: 3 * 70.906 / 232.41 = 0.915
  dichlor_available_chlorine: 2 * 70.906 / 255.97 = 0.554 (dihydrate)
  trichlor_cya_per_fc: 129.07 / (3 * 70.906) = 0.607
  dichlor_cya_per_fc: 129.07 / (2 * 70.906) = 0.910
  cal_hypo_ch_per_fc: 100.087 / (2 * 70.906) = 0.706
validation:
  - 10 ppm FC from trichlor adds about 6 ppm CYA (public TFP fact)
  - 10 ppm FC from dichlor adds about 9 ppm CYA (public TFP fact)
  - 10 ppm FC from cal-hypo adds about 7 ppm CH (public TFP fact)
```

Liquid chlorine also reports a salt side effect: hypochlorite manufacture
(`Cl2 + 2 NaOH`) yields equimolar NaCl and spent NaOCl ends as NaCl, so each
ppm of FC adds about `2 * 58.443 / 70.906 = 1.65` ppm salt.

## pH Lowering (muriatic acid) - approximate

pH dosing is buffer math, not ppm mass math, so this result is marked
approximate (`confidence: medium`).

```yaml
name: muriatic_acid_ph_lower
category: acid_base
source_note: closed-system carbonate buffer model with cyanurate/borate corrections
inputs:
  pool_gallons: gallons
  current_ph: required
  target_ph: required
  ta: ppm as CaCO3, required
  cya: ppm, optional
  borates: ppm, optional
  acid_percent: 31.45 (default) or 14.5
outputs:
  dose_fl_oz: fluid ounces
  effects: expected TA drop in ppm
formula: |
  carbonate_alk = ta - cyanurate_alk(ph) - borate_alk(ph)
  acid_ppm = carbonate_alk * (1 - r_t/r_0) / (1 + r_t)      # r = 10^(ph - 6.3)
           + buffer_alk(ph_now) - buffer_alk(ph_target)      # cyanurate + borate
  fl_oz = acid_ppm * fl_oz_per_ppm(strength, density)
constants:
  carbonic_pk1: 6.3
  cyanuric_pka: 6.9
  borate_pka: 9.2
  hcl_molar_mass: 36.461
  acid_31.45_density: 1.16 g/mL
assumptions:
  - real acid demand varies with aeration and CO2 exchange
  - TA drops by about the ppm of alkalinity the acid consumes
validation:
  - 1 gallon of 31.45 percent muriatic acid lowers TA by about 50 ppm in
    10,000 gallons (public identity; the model reproduces this exactly)
  - pH 7.8 -> 7.5 at TA 100, CYA 40, 10k gal = about 10 fl oz
```

## pH Raising (soda ash) - approximate

Marked `confidence: low`. Aeration raises pH without adding TA and is usually
the better first step; the dose card says so.

```yaml
name: soda_ash_ph_raise
category: acid_base
source_note: closed-system carbonate buffer model with cyanurate/borate corrections
inputs:
  pool_gallons: gallons
  current_ph: required
  target_ph: required
  ta: ppm as CaCO3, required
  cya: ppm, optional
  borates: ppm, optional
outputs:
  dose_oz_weight: ounces by weight
  effects: expected TA rise in ppm
formula: |
  base_ppm = (r_t * co2_0 - carbonate_alk) / (1 + r_t/2)
           + buffer_alk(ph_target) - buffer_alk(ph_now)
  product_lbs = ppm_to_pounds(base_ppm) * (105.988/2) / 50.042
validation:
  - pH 7.2 -> 7.5 at TA 70, CYA 40, 10k gal = about 12 oz, matching the
    common public chart value of about 3/4 lb soda ash
```

## SLAM Dose

SLAM is the existing liquid chlorine dose pointed at the FC/CYA chart's shock
level instead of the maintenance target. No new constants. The result warns
that SLAM is a process (hold FC at shock level, retest often, pass criteria:
CC under 0.5, overnight FC loss under 1 ppm, clear water).

## Dilution / Water Replacement

```yaml
name: lower_by_dilution
category: operations
source_note: proportional water replacement
inputs:
  pool_gallons: gallons
  current_ppm: reading being lowered (CYA, salt, CH, borates)
  target_ppm: desired reading
outputs:
  gallons_to_replace: drain-then-refill volume
  percent_of_pool: same as a percent
  gallons_if_draining_while_filling: exponential-decay volume
formula: |
  replace_fraction = 1 - target / current
  continuous_gallons = pool_gallons * ln(current / target)
validation:
  - halving CYA requires replacing half the water (100 -> 50 in 20k gal =
    10,000 gallons; about 13,860 if draining while filling)
```

## SWG Runtime Estimate

```yaml
name: swg_runtime
category: operations
source_note: cell rating arithmetic; ratings are lbs Cl2 gas per 24 h at 100 percent
inputs:
  pool_gallons: gallons
  cell_lbs_per_day: rated output at 100 percent
  target_fc_per_day: ppm FC to generate daily
  pump_hours_per_day: default 24
outputs:
  percent: required output setting (capped at 100 with a warning)
  hours_per_day_at_100_percent: equivalent runtime
formula: percent = target_fc_per_day / (cell_ppm_per_day * pump_hours / 24) * 100
assumptions:
  - output scales linearly with the percent setting
  - the cell only generates while the pump runs
validation:
  - a 1.4 lb/day cell in 10,000 gallons makes about 16.8 ppm/day at 100
    percent, so 4 ppm/day needs about 24 percent at 24 h pump runtime
```

## FC/CYA Targets

`openpool` encodes public Trouble Free Pool style FC/CYA target rows by hand.
CYA readings are rounded up to the next supported bucket. This is conservative:
the app should not recommend a lower FC target because a CYA test landed between
chart rows.

