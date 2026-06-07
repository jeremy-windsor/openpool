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

## FC/CYA Targets

`openpool` encodes public Trouble Free Pool style FC/CYA target rows by hand.
CYA readings are rounded up to the next supported bucket. This is conservative:
the app should not recommend a lower FC target because a CYA test landed between
chart rows.

