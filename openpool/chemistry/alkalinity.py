from __future__ import annotations

from openpool.chemistry.dosing import Dose
from openpool.chemistry.units import pounds_to_ounces, ppm_to_pounds, rounded

# TA is expressed as ppm CaCO3 (molar mass 100.09, 2 equivalents per mole).
# Sodium bicarbonate (84.006 g/mol) provides 1 equivalent per mole, so the
# product mass is the CaCO3-equivalent mass times 2 * 84.006 / 100.09.
NAHCO3_MOLAR_MASS = 84.006
CACO3_MOLAR_MASS = 100.09
BAKING_SODA_FACTOR = 2 * NAHCO3_MOLAR_MASS / CACO3_MOLAR_MASS


def dose_baking_soda_for_ta(
    pool_gallons: float,
    current_ta: float,
    target_ta: float,
) -> Dose:
    """Calculate a total alkalinity raise dose using sodium bicarbonate."""

    if pool_gallons <= 0:
        raise ValueError("pool volume must be greater than zero")

    formula = "product_lbs = delta_ta * pool_gallons * 8.345404452 / 1000000 * 1.679"
    assumptions = [
        "TA is measured as ppm CaCO3.",
        "Baking soda is pure sodium bicarbonate.",
        "Pool water is well mixed.",
    ]

    delta_ta = target_ta - current_ta
    if delta_ta <= 0:
        return Dose(
            chemical="baking_soda",
            amount=0.0,
            unit="oz_weight",
            warnings=["TA is lowered with acid plus aeration, not by a raising dose."],
            formula=formula,
            source_note="Stoichiometric ppm mass conversion.",
            assumptions=assumptions,
        )

    product_lbs = ppm_to_pounds(delta_ta, pool_gallons) * BAKING_SODA_FACTOR
    return Dose(
        chemical="baking_soda",
        amount=rounded(pounds_to_ounces(product_lbs), 1),
        unit="oz_weight",
        secondary={"pounds": rounded(product_lbs, 2)},
        warnings=[
            "Baking soda also nudges pH up slightly.",
            "Raise TA in steps and retest before adding more.",
        ],
        formula=formula,
        source_note="Stoichiometric ppm mass conversion.",
        assumptions=assumptions,
    )
