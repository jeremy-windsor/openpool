from __future__ import annotations

from openpool.chemistry.dosing import Dose
from openpool.chemistry.units import gallons_to_fl_oz, normalize_percent, rounded


def dose_liquid_chlorine_for_fc(
    pool_gallons: float,
    current_fc: float,
    target_fc: float,
    chlorine_percent: float = 10.0,
    jug_size_fl_oz: float | None = 128.0,
) -> Dose:
    """Dose liquid chlorine using the public pool-care identity.

    1 gallon of 10% sodium hypochlorite raises FC by about 10 ppm in
    10,000 gallons.
    """

    if pool_gallons <= 0:
        raise ValueError("pool volume must be greater than zero")

    delta_fc = target_fc - current_fc
    if delta_fc <= 0:
        return Dose(
            chemical="liquid_chlorine",
            amount=0.0,
            unit="fl_oz",
            warnings=[
                "No chemical dose is calculated for lowering FC; use sunlight, time, or dilution."
            ],
            formula="dose_gallons = delta_fc * pool_gallons / (10000 * chlorine_percent)",
            source_note="Public pool chemistry identity.",
            assumptions=[
                "1 gallon of 10% liquid chlorine raises FC by about 10 ppm in 10,000 gallons.",
                "Pool water is well mixed.",
            ],
        )

    strength = normalize_percent(chlorine_percent)
    dose_gallons = delta_fc * pool_gallons / (10_000 * strength)
    dose_fl_oz = gallons_to_fl_oz(dose_gallons)
    secondary = {"gallons": rounded(dose_gallons, 3)}

    if jug_size_fl_oz and jug_size_fl_oz > 0:
        secondary["jugs"] = rounded(dose_fl_oz / jug_size_fl_oz, 2)

    return Dose(
        chemical="liquid_chlorine",
        amount=rounded(dose_fl_oz, 1),
        unit="fl_oz",
        secondary=secondary,
        warnings=["pH readings can be unreliable when FC is high."],
        formula="dose_gallons = delta_fc * pool_gallons / (10000 * chlorine_percent)",
        source_note="Public pool chemistry identity.",
        assumptions=[
            "1 gallon of 10% liquid chlorine raises FC by about 10 ppm in 10,000 gallons.",
            "Pool water is well mixed.",
        ],
    )
