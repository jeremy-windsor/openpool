from __future__ import annotations

from math import isfinite

GALLON_TO_LITERS = 3.785411784
FL_OZ_PER_GALLON = 128.0
OZ_PER_LB = 16.0
WATER_LBS_PER_GALLON = 8.345404452


def gallons_to_liters(gallons: float) -> float:
    return gallons * GALLON_TO_LITERS


def liters_to_gallons(liters: float) -> float:
    return liters / GALLON_TO_LITERS


def gallons_to_fl_oz(gallons: float) -> float:
    return gallons * FL_OZ_PER_GALLON


def fl_oz_to_gallons(fl_oz: float) -> float:
    return fl_oz / FL_OZ_PER_GALLON


def pounds_to_ounces(pounds: float) -> float:
    return pounds * OZ_PER_LB


def ounces_to_pounds(ounces: float) -> float:
    return ounces / OZ_PER_LB


def ppm_to_pounds(ppm_delta: float, pool_gallons: float) -> float:
    """Convert a ppm change in water to pounds of pure solute.

    1 ppm is 1 part per million by mass. Pool calculators commonly use
    8.3454 lb/gal for water density, which is accurate enough for dosing.
    """

    return ppm_delta * pool_gallons * WATER_LBS_PER_GALLON / 1_000_000


def normalize_percent(percent: float) -> float:
    """Validate percent-only product strength semantics."""

    if not isfinite(percent):
        raise ValueError("percent strength must be a finite number")
    if 0 < percent < 1:
        raise ValueError(
            "enter product strength as a percent, e.g. 10 for a 10% product"
        )
    if percent <= 0 or percent > 100:
        raise ValueError("percent strength must be between 1 and 100")
    return percent


def require_finite_values(**values: float | None) -> None:
    """Reject non-finite chemistry inputs before any calculation."""

    for name, value in values.items():
        if value is not None and not isfinite(float(value)):
            raise ValueError(f"{name} must be a finite number")


def rounded(value: float, digits: int = 2) -> float:
    return round(value + 0.0, digits)
