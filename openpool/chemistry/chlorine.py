from __future__ import annotations

from openpool.chemistry.dosing import Dose
from openpool.chemistry.units import (
    gallons_to_fl_oz,
    normalize_percent,
    pounds_to_ounces,
    ppm_to_pounds,
    require_finite_values,
    rounded,
)

# FC is measured as ppm Cl2 (70.906 g/mol). Each dry product's strength is its
# available chlorine: grams of Cl2-equivalent oxidizing power per gram of
# product. Side effects fall straight out of the same stoichiometry.
CL2_MOLAR_MASS = 70.906
CYA_MOLAR_MASS = 129.07
CACO3_MOLAR_MASS = 100.087
NACL_MOLAR_MASS = 58.443

TRICHLOR_MOLAR_MASS = 232.41  # 3 Cl2-equivalents and 1 CYA per mole
DICHLOR_DIHYDRATE_MOLAR_MASS = 255.97  # 2 Cl2-equivalents and 1 CYA per mole

# Available chlorine fraction (Cl2-equivalent mass / product mass).
DRY_CHLORINE_PRODUCTS = {
    "trichlor": 3 * CL2_MOLAR_MASS / TRICHLOR_MOLAR_MASS,
    "dichlor": 2 * CL2_MOLAR_MASS / DICHLOR_DIHYDRATE_MOLAR_MASS,
    "cal_hypo": None,  # label strength varies; default below
}
CAL_HYPO_DEFAULT_PERCENT = 65.0
LIQUID_CHLORINE_TYPICAL_RANGE = (3.0, 15.0)
CAL_HYPO_TYPICAL_RANGE = (35.0, 78.0)
# Supported formulations, not a claim that other products cannot exist.
CHLORINE_STRENGTH_RANGES = {
    "liquid_chlorine": (1.0, 15.0),
    "cal_hypo": CAL_HYPO_TYPICAL_RANGE,
}
CHLORINE_ADDITION_CHEMICALS = frozenset(
    {"liquid_chlorine", "trichlor", "dichlor", "cal_hypo"}
)

# ppm of side effect per ppm of FC added, from molar ratios.
TRICHLOR_CYA_PER_FC = CYA_MOLAR_MASS / (3 * CL2_MOLAR_MASS)
DICHLOR_CYA_PER_FC = CYA_MOLAR_MASS / (2 * CL2_MOLAR_MASS)
CAL_HYPO_CH_PER_FC = CACO3_MOLAR_MASS / (2 * CL2_MOLAR_MASS)
# Hypochlorite manufacture (Cl2 + 2 NaOH) yields equimolar NaCl, and spent
# NaOCl also ends as NaCl, so each ppm FC adds about 2 moles of NaCl per Cl2.
LIQUID_CHLORINE_SALT_PER_FC = 2 * NACL_MOLAR_MASS / CL2_MOLAR_MASS


def validate_chlorine_strength(product: str, percent: float) -> float:
    strength = normalize_percent(percent)
    low, high = CHLORINE_STRENGTH_RANGES[product]
    if not low <= strength <= high:
        raise ValueError(f"{product} strength must be between {low:g} and {high:g} percent")
    return strength


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

    require_finite_values(
        pool_gallons=pool_gallons,
        current_fc=current_fc,
        target_fc=target_fc,
        chlorine_percent=chlorine_percent,
        jug_size_fl_oz=jug_size_fl_oz,
    )
    if pool_gallons <= 0:
        raise ValueError("pool volume must be greater than zero")

    strength = validate_chlorine_strength("liquid_chlorine", chlorine_percent)
    strength_warnings = []
    if not LIQUID_CHLORINE_TYPICAL_RANGE[0] <= strength <= LIQUID_CHLORINE_TYPICAL_RANGE[1]:
        strength_warnings.append(
            "Liquid chlorine is typically 3-15%; confirm the label strength."
        )

    delta_fc = target_fc - current_fc
    if delta_fc <= 0:
        return Dose(
            chemical="liquid_chlorine",
            amount=0.0,
            unit="fl_oz",
            warnings=strength_warnings + [
                "No chemical dose is calculated for lowering FC; use sunlight, time, or dilution."
            ],
            formula="dose_gallons = delta_fc * pool_gallons / (10000 * chlorine_percent)",
            source_note="Public pool chemistry identity.",
            assumptions=[
                "1 gallon of 10% liquid chlorine raises FC by about 10 ppm in 10,000 gallons.",
                "Pool water is well mixed.",
            ],
        )

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
        effects={"salt": rounded(delta_fc * LIQUID_CHLORINE_SALT_PER_FC, 1)},
        warnings=strength_warnings + ["pH readings can be unreliable when FC is high."],
        formula="dose_gallons = delta_fc * pool_gallons / (10000 * chlorine_percent)",
        source_note="Public pool chemistry identity.",
        assumptions=[
            "1 gallon of 10% liquid chlorine raises FC by about 10 ppm in 10,000 gallons.",
            "Pool water is well mixed.",
            "Salt effect counts the inherent NaCl in hypochlorite plus spent chlorine.",
        ],
    )


def dose_dry_chlorine_for_fc(
    pool_gallons: float,
    current_fc: float,
    target_fc: float,
    product: str,
    available_chlorine_percent: float | None = None,
) -> Dose:
    """Dose trichlor, dichlor, or cal-hypo by available-chlorine mass math.

    These products change more than FC: trichlor and dichlor add CYA (and
    trichlor is strongly acidic), cal-hypo adds calcium hardness. The expected
    side effects are returned so the calculator can show them.
    """

    require_finite_values(
        pool_gallons=pool_gallons,
        current_fc=current_fc,
        target_fc=target_fc,
        available_chlorine_percent=available_chlorine_percent,
    )
    if pool_gallons <= 0:
        raise ValueError("pool volume must be greater than zero")
    if product not in DRY_CHLORINE_PRODUCTS:
        raise ValueError("product must be trichlor, dichlor, or cal_hypo")

    if product == "cal_hypo":
        strength = validate_chlorine_strength(
            product,
            CAL_HYPO_DEFAULT_PERCENT
            if available_chlorine_percent is None
            else available_chlorine_percent
        )
        fraction = strength / 100
    else:
        fraction = DRY_CHLORINE_PRODUCTS[product]

    formula = "product_lbs = delta_fc * pool_gallons * 8.345404452 / 1000000 / available_chlorine"
    source_note = "Stoichiometric available-chlorine mass conversion."
    assumptions = [
        "FC is measured as ppm Cl2.",
        f"Available chlorine fraction {fraction:.3f} for {product}.",
        "Pool water is well mixed.",
    ]

    delta_fc = target_fc - current_fc
    if delta_fc <= 0:
        return Dose(
            chemical=product,
            amount=0.0,
            unit="oz_weight",
            warnings=[
                "No chemical dose is calculated for lowering FC; use sunlight, time, or dilution."
            ],
            formula=formula,
            source_note=source_note,
            assumptions=assumptions,
        )

    effects: dict[str, float] = {}
    warnings: list[str] = []
    if product == "trichlor":
        effects["cya"] = rounded(delta_fc * TRICHLOR_CYA_PER_FC, 1)
        warnings.append("Trichlor is strongly acidic; expect pH and TA to drift down.")
        warnings.append("CYA builds up with every dose and only leaves by dilution.")
    elif product == "dichlor":
        effects["cya"] = rounded(delta_fc * DICHLOR_CYA_PER_FC, 1)
        warnings.append("CYA builds up with every dose and only leaves by dilution.")
    else:
        effects["ch"] = rounded(delta_fc * CAL_HYPO_CH_PER_FC, 1)
        warnings.append("Cal-hypo raises calcium hardness; watch CH and CSI over time.")
        warnings.append("Pre-dissolve cal-hypo; never mix it with other chemicals.")

    product_lbs = ppm_to_pounds(delta_fc, pool_gallons) / fraction
    return Dose(
        chemical=product,
        amount=rounded(pounds_to_ounces(product_lbs), 1),
        unit="oz_weight",
        secondary={"pounds": rounded(product_lbs, 2)},
        effects=effects,
        warnings=warnings,
        formula=formula,
        source_note=source_note,
        assumptions=assumptions,
    )
