from __future__ import annotations

from openpool.chemistry.dosing import Dose
from openpool.chemistry.units import pounds_to_ounces, ppm_to_pounds, rounded

# pH dosing is buffer math, not simple ppm mass math. The model here treats
# pool water as a closed carbonate system plus the cyanurate and borate
# buffers, computes how much strong acid (or base) it takes to move every
# buffer from the current pH to the target pH, and converts that demand into
# product mass. Results are approximate by design and are labeled that way.

# Apparent first dissociation constant of carbonic acid in fresh water (~25 C).
CARBONIC_PK1 = 6.3
# Cyanuric acid first pKa under pool conditions.
CYANURIC_PKA = 6.9
# Boric acid pKa (matches the CSI borate correction).
BORATE_PKA = 9.2

CACO3_EQUIVALENT_MASS = 50.042  # g per equivalent (100.09 g/mol, 2 eq/mol)
HCL_MOLAR_MASS = 36.461
CYA_AS_CACO3 = 50.042 / 129.07  # ppm CYA -> ppm CaCO3 alkalinity equivalent
SODA_ASH_EQUIVALENT_MASS = 105.988 / 2  # Na2CO3, 2 eq/mol

# Muriatic acid products: mass fraction HCl and solution density (g/mL).
# 31.45 percent is 20 Baume, the common US pool acid.
ACID_PRODUCTS = {
    31.45: 1.16,
    14.5: 1.07,
}
ML_PER_FL_OZ = 29.5735
GRAMS_PER_POUND = 453.592


def _ionized_fraction(ph: float, pka: float) -> float:
    return 1 / (1 + 10 ** (pka - ph))


def _buffer_alkalinity(ph: float, cya: float | None, borates: float | None) -> float:
    """Cyanurate plus borate alkalinity (ppm CaCO3) at a given pH."""
    alk = 0.0
    if cya:
        alk += float(cya) * CYA_AS_CACO3 * _ionized_fraction(ph, CYANURIC_PKA)
    if borates:
        alk += float(borates) * _ionized_fraction(ph, BORATE_PKA)
    return alk


def acid_demand_ppm(
    ph_now: float,
    ph_target: float,
    ta: float,
    cya: float | None = None,
    borates: float | None = None,
) -> float:
    """Strong acid needed to lower pH, as ppm CaCO3 alkalinity consumed.

    Closed-system carbonate model: acid converts HCO3- to dissolved CO2, so
    the bicarbonate/CO2 ratio (which sets pH) shifts on both sides at once.
    The cyanurate and borate buffers release their stored alkalinity over the
    same pH interval and are added on top.
    """

    carbonate_alk = float(ta) - _buffer_alkalinity(ph_now, cya, borates)
    if carbonate_alk <= 0:
        raise ValueError("corrected carbonate alkalinity must be positive")

    ratio_now = 10 ** (ph_now - CARBONIC_PK1)
    ratio_target = 10 ** (ph_target - CARBONIC_PK1)
    carbonate_demand = carbonate_alk * (1 - ratio_target / ratio_now) / (1 + ratio_target)
    buffer_demand = _buffer_alkalinity(ph_now, cya, borates) - _buffer_alkalinity(
        ph_target, cya, borates
    )
    return carbonate_demand + buffer_demand


def base_demand_ppm(
    ph_now: float,
    ph_target: float,
    ta: float,
    cya: float | None = None,
    borates: float | None = None,
) -> float:
    """Soda ash needed to raise pH, as ppm CaCO3 alkalinity added.

    Soda ash adds carbonate, which consumes dissolved CO2 and adds
    bicarbonate, so it moves the carbonate ratio from both sides. The
    cyanurate and borate buffers absorb part of the base over the interval.
    """

    carbonate_alk = float(ta) - _buffer_alkalinity(ph_now, cya, borates)
    if carbonate_alk <= 0:
        raise ValueError("corrected carbonate alkalinity must be positive")

    ratio_now = 10 ** (ph_now - CARBONIC_PK1)
    ratio_target = 10 ** (ph_target - CARBONIC_PK1)
    co2_now = carbonate_alk / ratio_now
    carbonate_demand = (ratio_target * co2_now - carbonate_alk) / (1 + ratio_target / 2)
    buffer_demand = _buffer_alkalinity(ph_target, cya, borates) - _buffer_alkalinity(
        ph_now, cya, borates
    )
    return carbonate_demand + buffer_demand


def _acid_fl_oz_per_ppm(pool_gallons: float, acid_percent: float, density: float) -> float:
    grams_caco3 = ppm_to_pounds(1.0, pool_gallons) * GRAMS_PER_POUND
    grams_hcl = grams_caco3 / CACO3_EQUIVALENT_MASS * HCL_MOLAR_MASS
    solution_ml = grams_hcl / (acid_percent / 100) / density
    return solution_ml / ML_PER_FL_OZ


def dose_muriatic_acid_for_ph(
    pool_gallons: float,
    current_ph: float,
    target_ph: float,
    ta: float,
    cya: float | None = None,
    borates: float | None = None,
    acid_percent: float = 31.45,
) -> Dose:
    """Approximate muriatic acid dose to lower pH, with the expected TA drop."""

    if pool_gallons <= 0:
        raise ValueError("pool volume must be greater than zero")
    if ta <= 0:
        raise ValueError("TA is required to estimate acid demand")
    if acid_percent not in ACID_PRODUCTS:
        supported = ", ".join(f"{pct:g}" for pct in sorted(ACID_PRODUCTS))
        raise ValueError(f"supported muriatic acid strengths: {supported} percent")

    formula = "acid_ppm = carbonate + cyanurate + borate buffer demand from pH to target pH"
    source_note = (
        "Closed-system carbonate buffer model with cyanurate/borate corrections; "
        "acid volume anchored to the public identity that 1 gallon of 31.45 "
        "percent muriatic acid lowers TA by about 50 ppm in 10,000 gallons."
    )
    assumptions = [
        "Approximate: real acid demand varies with aeration and CO2 exchange.",
        f"Carbonic acid pK1 {CARBONIC_PK1}, cyanuric pKa {CYANURIC_PKA}, borate pKa {BORATE_PKA}.",
        "TA drops by about the same ppm of alkalinity the acid consumes.",
    ]

    if target_ph >= current_ph:
        return Dose(
            chemical="muriatic_acid",
            amount=0.0,
            unit="fl_oz",
            warnings=["Target pH is not below current pH; no acid is needed."],
            formula=formula,
            source_note=source_note,
            assumptions=assumptions,
            confidence="medium",
        )

    demand_ppm = acid_demand_ppm(current_ph, target_ph, ta, cya, borates)
    fl_oz = demand_ppm * _acid_fl_oz_per_ppm(
        pool_gallons, acid_percent, ACID_PRODUCTS[acid_percent]
    )
    return Dose(
        chemical="muriatic_acid",
        amount=rounded(fl_oz, 1),
        unit="fl_oz",
        secondary={"cups": rounded(fl_oz / 8, 2)},
        effects={"ta": rounded(-demand_ppm, 1)},
        warnings=[
            "Add acid slowly with the pump running; never add water to acid.",
            "pH readings are unreliable when FC is very high (during SLAM).",
            "Retest pH after 30-60 minutes of circulation before re-dosing.",
        ],
        formula=formula,
        source_note=source_note,
        assumptions=assumptions + [f"Acid strength {acid_percent:g} percent HCl."],
        confidence="medium",
    )


def dose_soda_ash_for_ph(
    pool_gallons: float,
    current_ph: float,
    target_ph: float,
    ta: float,
    cya: float | None = None,
    borates: float | None = None,
) -> Dose:
    """Approximate soda ash dose to raise pH, with the expected TA rise."""

    if pool_gallons <= 0:
        raise ValueError("pool volume must be greater than zero")
    if ta <= 0:
        raise ValueError("TA is required to estimate base demand")

    formula = "base_ppm = carbonate + cyanurate + borate buffer demand from pH to target pH"
    source_note = (
        "Closed-system carbonate buffer model with cyanurate/borate corrections; "
        "cross-checked against the common chart value of about 3/4 lb soda ash "
        "to move 10,000 gallons from pH 7.2 to 7.5."
    )
    assumptions = [
        "Approximate: real base demand varies with aeration and CO2 exchange.",
        "Soda ash is pure sodium carbonate (105.99 g/mol, 2 equivalents per mole).",
        "TA rises by about the same ppm of alkalinity the soda ash adds.",
    ]

    if target_ph <= current_ph:
        return Dose(
            chemical="soda_ash",
            amount=0.0,
            unit="oz_weight",
            warnings=["Target pH is not above current pH; no soda ash is needed."],
            formula=formula,
            source_note=source_note,
            assumptions=assumptions,
            confidence="low",
        )

    demand_ppm = base_demand_ppm(current_ph, target_ph, ta, cya, borates)
    product_lbs = (
        ppm_to_pounds(demand_ppm, pool_gallons)
        * SODA_ASH_EQUIVALENT_MASS
        / CACO3_EQUIVALENT_MASS
    )
    return Dose(
        chemical="soda_ash",
        amount=rounded(pounds_to_ounces(product_lbs), 1),
        unit="oz_weight",
        secondary={"pounds": rounded(product_lbs, 2)},
        effects={"ta": rounded(demand_ppm, 1)},
        warnings=[
            "Aeration raises pH without adding TA and is often the better first step.",
            "Soda ash also raises TA; if TA is already high, prefer aeration.",
            "Add in steps and retest after 30-60 minutes of circulation.",
        ],
        formula=formula,
        source_note=source_note,
        assumptions=assumptions,
        confidence="low",
    )
