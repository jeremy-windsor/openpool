from __future__ import annotations

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
    """Accept either 10 or 0.10 for a ten-percent product strength."""

    if percent <= 0:
        raise ValueError("percent strength must be greater than zero")
    if percent <= 1:
        return percent * 100
    return percent


def rounded(value: float, digits: int = 2) -> float:
    return round(value + 0.0, digits)

