from __future__ import annotations

from dataclasses import dataclass, field
from math import log10

# CSI here is the Langelier-style saturation index with pool-specific
# corrections: carbonate alkalinity is total alkalinity minus the cyanurate
# and borate contributions. The result is approximate by design; it is a
# scale/corrosion trend signal, not a lab measurement.

DEFAULT_TDS_PPM = 1000.0
DEFAULT_WATER_TEMP_F = 80.0
CYA_ALKALINITY_FACTOR = 0.33  # fraction of CYA counted as alkalinity near pH 7.5
BORATE_PKA = 9.2


@dataclass(frozen=True)
class CsiResult:
    value: float | None
    warnings: list[str] = field(default_factory=list)


def calculate_csi(
    ph: float | None,
    ta: float | None,
    ch: float | None,
    cya: float | None = None,
    water_temp_f: float | None = None,
    salt: float | None = None,
    borates: float | None = None,
) -> CsiResult:
    """Approximate the Calcite Saturation Index for pool water.

    Requires pH, TA, and CH. CYA, temperature, salt (as a TDS stand-in), and
    borates refine the result when present; missing optional inputs fall back
    to documented defaults and add a warning instead of failing.
    """

    missing = [name for name, value in (("pH", ph), ("TA", ta), ("CH", ch)) if value is None]
    if missing:
        return CsiResult(None, [f"CSI needs pH, TA, and CH; missing {', '.join(missing)}."])

    warnings: list[str] = []

    carbonate_alk = float(ta)
    if cya is not None:
        carbonate_alk -= CYA_ALKALINITY_FACTOR * float(cya)
    else:
        warnings.append("No CYA reading; cyanurate alkalinity correction skipped.")
    if borates:
        # Fraction of borate ionized at this pH (boric acid pKa ~9.2).
        carbonate_alk -= float(borates) / (1 + 10 ** (BORATE_PKA - float(ph)))
    if carbonate_alk <= 0 or float(ch) <= 0:
        return CsiResult(
            None, ["Corrected carbonate alkalinity or CH is not positive; CSI is undefined."]
        )

    if water_temp_f is None:
        water_temp_f = DEFAULT_WATER_TEMP_F
        warnings.append(f"No water temperature; assuming {DEFAULT_WATER_TEMP_F:g} F.")
    if salt is None:
        tds = DEFAULT_TDS_PPM
        warnings.append(f"No salt reading; assuming {DEFAULT_TDS_PPM:g} ppm TDS.")
    else:
        tds = max(float(salt), DEFAULT_TDS_PPM)

    temp_c = (float(water_temp_f) - 32) * 5 / 9
    tds_factor = (log10(tds) - 1) / 10
    temp_factor = -13.12 * log10(temp_c + 273) + 34.55
    calcium_factor = log10(float(ch)) - 0.4
    alkalinity_factor = log10(carbonate_alk)

    ph_saturation = 9.3 + tds_factor + temp_factor - (calcium_factor + alkalinity_factor)
    return CsiResult(round(float(ph) - ph_saturation, 2), warnings)
