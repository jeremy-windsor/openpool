from __future__ import annotations

from openpool.chemistry.dosing import Dose
from openpool.chemistry.units import ppm_to_pounds, rounded


def dose_salt_for_ppm(
    pool_gallons: float,
    current_salt: float,
    target_salt: float,
    bag_size_lbs: float | None = 40.0,
) -> Dose:
    if pool_gallons <= 0:
        raise ValueError("pool volume must be greater than zero")

    delta_salt = target_salt - current_salt
    if delta_salt <= 0:
        return Dose(
            chemical="salt",
            amount=0.0,
            unit="lb",
            warnings=["Salt is lowered by dilution or water replacement, not by a chemical dose."],
            formula="lbs_salt = delta_salt_ppm * pool_gallons * 8.345404452 / 1000000",
            source_note="ppm mass conversion.",
            assumptions=["Salt test readings are close enough for practical dosing."],
        )

    pounds = ppm_to_pounds(delta_salt, pool_gallons)
    secondary = {}
    if bag_size_lbs and bag_size_lbs > 0:
        secondary["bags"] = rounded(pounds / bag_size_lbs, 2)

    return Dose(
        chemical="salt",
        amount=rounded(pounds, 1),
        unit="lb",
        secondary=secondary,
        warnings=["Raise salt slowly and retest before chasing small deltas."],
        formula="lbs_salt = delta_salt_ppm * pool_gallons * 8.345404452 / 1000000",
        source_note="ppm mass conversion.",
        assumptions=["Salt test readings are close enough for practical dosing."],
    )
