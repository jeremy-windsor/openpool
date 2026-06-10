from __future__ import annotations

import pytest

from openpool.chemistry.acid_base import (
    _acid_fl_oz_per_ppm,
    dose_muriatic_acid_for_ph,
    dose_soda_ash_for_ph,
)
from openpool.chemistry.chlorine import dose_dry_chlorine_for_fc, dose_liquid_chlorine_for_fc
from openpool.chemistry.cya import dose_dry_stabilizer_for_cya
from openpool.chemistry.operations import estimate_drain_for_dilution, estimate_swg_runtime
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


def test_dry_chlorine_reference_cases(reference_examples):
    for case in reference_examples["dry_chlorine"]:
        dose = dose_dry_chlorine_for_fc(
            pool_gallons=case["pool_gallons"],
            current_fc=case["current_fc"],
            target_fc=case["target_fc"],
            product=case["product"],
        )
        assert dose.unit == "oz_weight"
        assert _within(dose.amount, case["expected_oz_weight"], case["tolerance_pct"]), case["name"]
        if "expected_cya_effect" in case:
            assert _within(
                dose.effects["cya"], case["expected_cya_effect"], case["tolerance_pct"]
            ), case["name"]
        if "expected_ch_effect" in case:
            assert _within(
                dose.effects["ch"], case["expected_ch_effect"], case["tolerance_pct"]
            ), case["name"]


def test_dry_chlorine_rejects_unknown_product():
    with pytest.raises(ValueError):
        dose_dry_chlorine_for_fc(10000, 0, 10, product="mystery_shock")


def test_liquid_chlorine_reports_salt_effect():
    dose = dose_liquid_chlorine_for_fc(10000, 0, 10)
    assert _within(dose.effects["salt"], 16.5, 3)


def test_muriatic_acid_reference_cases(reference_examples):
    anchor, derived = reference_examples["muriatic_acid"]
    # Public identity: 50 ppm of alkalinity demand is about 1 gallon of
    # 31.45 percent acid in 10,000 gallons.
    fl_oz = anchor["demand_ppm"] * _acid_fl_oz_per_ppm(anchor["pool_gallons"], 31.45, 1.16)
    assert _within(fl_oz, anchor["expected_fl_oz"], anchor["tolerance_pct"]), anchor["name"]

    dose = dose_muriatic_acid_for_ph(
        pool_gallons=derived["pool_gallons"],
        current_ph=derived["current_ph"],
        target_ph=derived["target_ph"],
        ta=derived["ta"],
        cya=derived["cya"],
    )
    assert dose.unit == "fl_oz"
    assert dose.confidence == "medium"
    assert _within(dose.amount, derived["expected_fl_oz"], derived["tolerance_pct"])
    assert _within(-dose.effects["ta"], derived["expected_ta_drop"], derived["tolerance_pct"])


def test_muriatic_acid_zero_dose_when_target_above_current():
    dose = dose_muriatic_acid_for_ph(10000, 7.4, 7.6, ta=80)
    assert dose.amount == 0.0
    assert dose.warnings


def test_muriatic_acid_requires_ta():
    with pytest.raises(ValueError):
        dose_muriatic_acid_for_ph(10000, 7.8, 7.5, ta=0)


def test_soda_ash_reference_case(reference_examples):
    case = reference_examples["soda_ash"][0]
    dose = dose_soda_ash_for_ph(
        pool_gallons=case["pool_gallons"],
        current_ph=case["current_ph"],
        target_ph=case["target_ph"],
        ta=case["ta"],
        cya=case["cya"],
    )
    assert dose.unit == "oz_weight"
    assert dose.confidence == "low"
    assert _within(dose.amount, case["expected_oz_weight"], case["tolerance_pct"]), case["name"]
    assert _within(dose.secondary["pounds"], case["expected_pounds"], case["tolerance_pct"])
    assert dose.effects["ta"] > 0


def test_dilution_reference_case(reference_examples):
    case = reference_examples["dilution"][0]
    dose = estimate_drain_for_dilution(
        pool_gallons=case["pool_gallons"],
        current_ppm=case["current_ppm"],
        target_ppm=case["target_ppm"],
    )
    assert dose.unit == "gallons"
    assert _within(dose.amount, case["expected_gallons"], case["tolerance_pct"]), case["name"]
    assert _within(dose.secondary["percent_of_pool"], case["expected_percent"], 1)
    assert _within(
        dose.secondary["gallons_if_draining_while_filling"],
        case["expected_continuous_gallons"],
        case["tolerance_pct"],
    )


def test_dilution_zero_when_target_not_below_current():
    dose = estimate_drain_for_dilution(20000, 50, 60)
    assert dose.amount == 0.0
    assert dose.warnings


def test_swg_runtime_reference_cases(reference_examples):
    for case in reference_examples["swg_runtime"]:
        dose = estimate_swg_runtime(
            pool_gallons=case["pool_gallons"],
            cell_lbs_per_day=case["cell_lbs_per_day"],
            target_fc_per_day=case["target_fc_per_day"],
            pump_hours_per_day=case["pump_hours_per_day"],
        )
        assert dose.unit == "percent"
        assert _within(dose.amount, case["expected_percent"], case["tolerance_pct"]), case["name"]
        assert _within(
            dose.secondary["cell_ppm_per_day_at_100_percent"],
            case["expected_ppm_per_day_at_100"],
            case["tolerance_pct"],
        ), case["name"]


def test_swg_runtime_warns_when_cell_cannot_keep_up():
    dose = estimate_swg_runtime(30000, 0.7, 4, pump_hours_per_day=6)
    assert dose.amount == 100.0
    assert dose.secondary["required_percent"] > 100
    assert any("cannot make this much" in warning for warning in dose.warnings)
