from __future__ import annotations

from openpool.chemistry.dosing import Dose
from openpool.chemistry.units import pounds_to_ounces, ppm_to_pounds, rounded


def dose_dry_stabilizer_for_cya(
    pool_gallons: float,
    current_cya: float,
    target_cya: float,
    product_purity: float = 1.0,
) -> Dose:
    """Calculate dry cyanuric acid dose by ppm mass math."""

    if pool_gallons <= 0:
        raise ValueError("pool volume must be greater than zero")
    if not 0 < product_purity <= 1:
        raise ValueError("product purity must be between 0 and 1")

    delta_cya = target_cya - current_cya
    if delta_cya <= 0:
        return Dose(
            chemical="dry_stabilizer",
            amount=0.0,
            unit="oz_weight",
            warnings=["CYA is lowered by dilution or water replacement, not by a chemical dose."],
            formula="product_lbs = delta_cya * pool_gallons * 8.345404452 / 1000000 / purity",
            source_note="ppm mass conversion.",
            assumptions=[
                "CYA ppm is treated as ppm by mass in pool water.",
                "Product purity defaults to 100 percent unless configured.",
            ],
        )

    pure_lbs = ppm_to_pounds(delta_cya, pool_gallons)
    product_lbs = pure_lbs / product_purity
    return Dose(
        chemical="dry_stabilizer",
        amount=rounded(pounds_to_ounces(product_lbs), 1),
        unit="oz_weight",
        secondary={"pounds": rounded(product_lbs, 2)},
        warnings=["CYA dissolves slowly; wait before retesting and adjusting again."],
        formula="product_lbs = delta_cya * pool_gallons * 8.345404452 / 1000000 / purity",
        source_note="ppm mass conversion.",
        assumptions=[
            "CYA ppm is treated as ppm by mass in pool water.",
            "Product purity defaults to 100 percent unless configured.",
        ],
    )
