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

## FC/CYA Targets

`openpool` encodes public Trouble Free Pool style FC/CYA target rows by hand.
CYA readings are rounded up to the next supported bucket. This is conservative:
the app should not recommend a lower FC target because a CYA test landed between
chart rows.

