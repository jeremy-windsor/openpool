from __future__ import annotations

import pytest

from openpool.chemistry.chlorine import dose_liquid_chlorine_for_fc
from openpool.chemistry.cya import dose_dry_stabilizer_for_cya
from openpool.chemistry.salt import dose_salt_for_ppm
from openpool.chemistry.targets import fc_cya_targets
from openpool.chemistry.units import normalize_percent, ppm_to_pounds


def _within(actual: float, expected: float, tolerance_pct: float) -> bool:
    if expected == 0:
        return abs(actual) <= tolerance_pct / 100
    return abs(actual - expected) / abs(expected) <= tolerance_pct / 100


def test_liquid_chlorine_reference_cases(reference_examples):
    for case in reference_examples["liquid_chlorine"]:
        dose = dose_liquid_chlorine_for_fc(
            pool_gallons=case["pool_gallons"],
            current_fc=case["current_fc"],
            target_fc=case["target_fc"],
            chlorine_percent=case["chlorine_percent"],
        )
        assert dose.unit == "fl_oz"
        assert _within(dose.amount, case["expected_fl_oz"], case["tolerance_pct"]), case["name"]
        assert _within(
            dose.secondary["gallons"], case["expected_gallons"], case["tolerance_pct"]
        ), case["name"]


def test_dry_stabilizer_reference_cases(reference_examples):
    for case in reference_examples["dry_stabilizer"]:
        dose = dose_dry_stabilizer_for_cya(
            pool_gallons=case["pool_gallons"],
            current_cya=case["current_cya"],
            target_cya=case["target_cya"],
        )
        assert dose.unit == "oz_weight"
        assert _within(dose.amount, case["expected_oz_weight"], case["tolerance_pct"]), case["name"]
        assert _within(
            dose.secondary["pounds"], case["expected_pounds"], case["tolerance_pct"]
        ), case["name"]


def test_salt_reference_cases(reference_examples):
    for case in reference_examples["salt"]:
        dose = dose_salt_for_ppm(
            pool_gallons=case["pool_gallons"],
            current_salt=case["current_salt"],
            target_salt=case["target_salt"],
        )
        assert dose.unit == "lb"
        assert _within(dose.amount, case["expected_pounds"], case["tolerance_pct"]), case["name"]
        assert _within(dose.secondary["bags"], case["expected_bags"], case["tolerance_pct"]), case[
            "name"
        ]


def test_fc_cya_target_reference_cases(reference_examples):
    for case in reference_examples["fc_cya_targets"]:
        targets = fc_cya_targets(case["cya"], sanitizer=case["sanitizer"])
        assert targets.cya == case["expected_bucket"], case["name"]
        assert targets.minimum == case["expected_minimum"], case["name"]
        assert targets.target_low == case["expected_target_low"], case["name"]
        assert targets.target_high == case["expected_target_high"], case["name"]
        assert targets.slam == case["expected_slam"], case["name"]


def test_no_negative_chlorine_dose():
    dose = dose_liquid_chlorine_for_fc(
        pool_gallons=10_000, current_fc=8, target_fc=5, chlorine_percent=10
    )
    assert dose.amount == 0
    assert dose.warnings


def test_chlorine_jug_count_uses_jug_size():
    dose = dose_liquid_chlorine_for_fc(
        pool_gallons=20_000,
        current_fc=2,
        target_fc=7,
        chlorine_percent=10,
        jug_size_fl_oz=128.0,
    )
    # 5 ppm in 20k gal at 10% = 1.0 gal = 128 fl oz = 1 jug.
    assert dose.secondary["jugs"] == pytest.approx(1.0, abs=0.01)


def test_cya_bucket_rounds_up_conservatively():
    targets = fc_cya_targets(35, sanitizer="liquid_chlorine")
    assert targets.cya == 40


def test_cya_above_chart_warns():
    targets = fc_cya_targets(200, sanitizer="liquid_chlorine")
    assert targets.cya == 100
    assert targets.warnings


def test_missing_cya_uses_lowest_bucket_and_warns():
    targets = fc_cya_targets(None, sanitizer="liquid_chlorine")
    assert targets.cya == 20
    assert targets.warnings


def test_zero_volume_rejected():
    with pytest.raises(ValueError):
        dose_liquid_chlorine_for_fc(pool_gallons=0, current_fc=1, target_fc=5)


def test_normalize_percent_accepts_fraction_or_whole():
    assert normalize_percent(0.10) == pytest.approx(10.0)
    assert normalize_percent(10) == pytest.approx(10.0)


def test_ppm_to_pounds_identity():
    # 1 ppm by mass in 1,000,000 lb of water equals 1 lb of solute.
    pounds = ppm_to_pounds(1, 1_000_000 / 8.345404452)
    assert pounds == pytest.approx(1.0, rel=1e-6)


def test_calcium_chloride_reference_cases(reference_examples):
    from openpool.chemistry.calcium import dose_calcium_chloride_for_ch

    for case in reference_examples["calcium_chloride"]:
        dose = dose_calcium_chloride_for_ch(
            pool_gallons=case["pool_gallons"],
            current_ch=case["current_ch"],
            target_ch=case["target_ch"],
            product=case["product"],
        )
        assert dose.unit == "oz_weight"
        assert _within(dose.amount, case["expected_oz_weight"], case["tolerance_pct"]), case["name"]
        assert _within(
            dose.secondary["pounds"], case["expected_pounds"], case["tolerance_pct"]
        ), case["name"]


def test_calcium_lowering_returns_zero_dose():
    from openpool.chemistry.calcium import dose_calcium_chloride_for_ch

    dose = dose_calcium_chloride_for_ch(pool_gallons=10_000, current_ch=500, target_ch=300)
    assert dose.amount == 0
    assert dose.warnings


def test_calcium_rejects_unknown_product():
    from openpool.chemistry.calcium import dose_calcium_chloride_for_ch

    with pytest.raises(ValueError):
        dose_calcium_chloride_for_ch(
            pool_gallons=10_000, current_ch=200, target_ch=250, product="limestone"
        )


def test_baking_soda_reference_cases(reference_examples):
    from openpool.chemistry.alkalinity import dose_baking_soda_for_ta

    for case in reference_examples["baking_soda"]:
        dose = dose_baking_soda_for_ta(
            pool_gallons=case["pool_gallons"],
            current_ta=case["current_ta"],
            target_ta=case["target_ta"],
        )
        assert dose.unit == "oz_weight"
        assert _within(dose.amount, case["expected_oz_weight"], case["tolerance_pct"]), case["name"]
        assert _within(
            dose.secondary["pounds"], case["expected_pounds"], case["tolerance_pct"]
        ), case["name"]


def test_baking_soda_lowering_returns_zero_dose():
    from openpool.chemistry.alkalinity import dose_baking_soda_for_ta

    dose = dose_baking_soda_for_ta(pool_gallons=10_000, current_ta=120, target_ta=80)
    assert dose.amount == 0
    assert dose.warnings


def test_csi_reference_cases(reference_examples):
    from openpool.chemistry.csi import calculate_csi

    for case in reference_examples["csi"]:
        result = calculate_csi(
            ph=case["ph"],
            ta=case["ta"],
            ch=case["ch"],
            cya=case.get("cya"),
            water_temp_f=case.get("water_temp_f"),
            salt=case.get("salt"),
        )
        assert result.value == pytest.approx(
            case["expected_csi"], abs=case["tolerance_abs"]
        ), case["name"]
        if "expected_warning_count" in case:
            assert len(result.warnings) == case["expected_warning_count"], case["name"]


def test_csi_requires_ph_ta_ch():
    from openpool.chemistry.csi import calculate_csi

    result = calculate_csi(ph=None, ta=70, ch=350)
    assert result.value is None
    assert "missing pH" in result.warnings[0]
