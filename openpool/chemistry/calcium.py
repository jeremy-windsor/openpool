from __future__ import annotations

from openpool.chemistry.dosing import Dose
from openpool.chemistry.units import pounds_to_ounces, ppm_to_pounds, rounded

# Molar masses (g/mol). CH is measured as ppm CaCO3, so product doses scale by
# the ratio of product molar mass to CaCO3 molar mass.
CACO3_MOLAR_MASS = 100.09
CACL2_MOLAR_MASS = 110.98
CACL2_DIHYDRATE_MOLAR_MASS = 147.01

PRODUCT_FACTORS = {
    "calcium_chloride": CACL2_MOLAR_MASS / CACO3_MOLAR_MASS,
    "calcium_chloride_dihydrate": CACL2_DIHYDRATE_MOLAR_MASS / CACO3_MOLAR_MASS,
}


def dose_calcium_chloride_for_ch(
    pool_gallons: float,
    current_ch: float,
    target_ch: float,
    product: str = "calcium_chloride_dihydrate",
) -> Dose:
    """Calculate a calcium hardness raise dose by ppm mass math.

    CH is expressed as ppm CaCO3, so the product dose is the CaCO3-equivalent
    mass scaled by the product/CaCO3 molar mass ratio. Most retail "calcium
    hardness increaser" is the dihydrate (77-80 percent products).
    """

    if pool_gallons <= 0:
        raise ValueError("pool volume must be greater than zero")
    if product not in PRODUCT_FACTORS:
        raise ValueError(
            "product must be calcium_chloride or calcium_chloride_dihydrate"
        )

    formula = (
        "product_lbs = delta_ch * pool_gallons * 8.345404452 / 1000000"
        " * (product_molar_mass / 100.09)"
    )
    assumptions = [
        "CH is measured as ppm CaCO3.",
        "Product purity is assumed 100 percent of the labeled compound.",
        "Pool water is well mixed.",
    ]

    delta_ch = target_ch - current_ch
    if delta_ch <= 0:
        return Dose(
            chemical=product,
            amount=0.0,
            unit="oz_weight",
            warnings=["CH is lowered by dilution or water replacement, not by a chemical dose."],
            formula=formula,
            source_note="Stoichiometric ppm mass conversion.",
            assumptions=assumptions,
        )

    product_lbs = ppm_to_pounds(delta_ch, pool_gallons) * PRODUCT_FACTORS[product]
    return Dose(
        chemical=product,
        amount=rounded(pounds_to_ounces(product_lbs), 1),
        unit="oz_weight",
        secondary={"pounds": rounded(product_lbs, 2)},
        warnings=[
            "Calcium chloride releases heat when dissolving; pre-dissolve and add slowly.",
            "Raise CH in steps and retest before adding more.",
        ],
        formula=formula,
        source_note="Stoichiometric ppm mass conversion.",
        assumptions=assumptions,
    )
