from __future__ import annotations

from math import log

from openpool.chemistry.dosing import Dose
from openpool.chemistry.units import ppm_to_pounds, rounded

# Operational helpers: not chemical doses, but the same Dose container keeps
# the units/warnings/assumptions contract consistent across the calculator.


def estimate_drain_for_dilution(
    pool_gallons: float,
    current_ppm: float,
    target_ppm: float,
) -> Dose:
    """Water replacement needed to lower a dilution-only parameter.

    Works for CYA, salt, CH, and borates: replacing a fraction of the water
    lowers the reading by the same fraction. This is proportional replacement
    math, nothing more.
    """

    if pool_gallons <= 0:
        raise ValueError("pool volume must be greater than zero")
    if current_ppm <= 0:
        raise ValueError("current reading must be greater than zero")

    formula = "replace_fraction = 1 - target / current"
    source_note = "Proportional water replacement."
    assumptions = [
        "Drained water is fully mixed pool water.",
        "Fill water contains none of the parameter being lowered.",
        "Fill water can add CH and TA; retest after refilling.",
    ]

    if target_ppm >= current_ppm:
        return Dose(
            chemical="water_replacement",
            amount=0.0,
            unit="gallons",
            warnings=["Target is not below current; no water replacement is needed."],
            formula=formula,
            source_note=source_note,
            assumptions=assumptions,
        )

    fraction = 1 - target_ppm / current_ppm
    gallons = fraction * pool_gallons
    # Draining and filling at the same time mixes new water into the drain
    # stream, so it follows exponential decay and needs more total water.
    continuous_gallons = pool_gallons * log(current_ppm / target_ppm)
    return Dose(
        chemical="water_replacement",
        amount=rounded(gallons, 0),
        unit="gallons",
        secondary={
            "percent_of_pool": rounded(fraction * 100, 1),
            "gallons_if_draining_while_filling": rounded(continuous_gallons, 0),
        },
        warnings=[
            "Drain first, then refill; draining while filling wastes water.",
            "Never drain below equipment limits; mind hydrostatic pressure on in-ground pools.",
        ],
        formula=formula,
        source_note=source_note,
        assumptions=assumptions,
    )


def estimate_swg_runtime(
    pool_gallons: float,
    cell_lbs_per_day: float,
    target_fc_per_day: float,
    pump_hours_per_day: float = 24.0,
) -> Dose:
    """SWG percent setting needed to generate a daily FC amount.

    Cells are rated in pounds of chlorine gas per 24 hours of runtime at 100
    percent output. FC is measured as ppm Cl2, so the rating converts straight
    to ppm per day for a given pool volume.
    """

    if pool_gallons <= 0:
        raise ValueError("pool volume must be greater than zero")
    if cell_lbs_per_day <= 0:
        raise ValueError("cell output rating must be greater than zero")
    if target_fc_per_day <= 0:
        raise ValueError("target FC per day must be greater than zero")
    if not 0 < pump_hours_per_day <= 24:
        raise ValueError("pump hours per day must be between 0 and 24")

    formula = (
        "percent = target_fc_per_day / (cell_ppm_per_day * pump_hours / 24) * 100"
    )
    source_note = "Cell rating arithmetic; ratings are lbs Cl2 gas per 24 h at 100 percent."
    assumptions = [
        "Cell output scales linearly with the percent setting.",
        "The cell only generates while the pump is running.",
        "Daily FC demand of 2-4 ppm is typical; sun, heat, and swimmers raise it.",
    ]

    cell_ppm_per_day = cell_lbs_per_day / ppm_to_pounds(1.0, pool_gallons)
    percent = target_fc_per_day / (cell_ppm_per_day * pump_hours_per_day / 24) * 100
    hours_at_100 = 24 * target_fc_per_day / cell_ppm_per_day

    warnings = ["Verify with FC tests over several days; cell output degrades with age."]
    if percent > 100:
        warnings.insert(
            0,
            "The cell cannot make this much chlorine in the configured pump runtime; "
            "run the pump longer or supplement with liquid chlorine.",
        )

    return Dose(
        chemical="swg_runtime",
        amount=rounded(min(percent, 100.0), 0),
        unit="percent",
        secondary={
            "required_percent": rounded(percent, 0),
            "hours_per_day_at_100_percent": rounded(hours_at_100, 1),
            "cell_ppm_per_day_at_100_percent": rounded(cell_ppm_per_day, 1),
        },
        warnings=warnings,
        formula=formula,
        source_note=source_note,
        assumptions=assumptions,
        confidence="medium",
    )
