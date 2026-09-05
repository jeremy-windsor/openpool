from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hmac import compare_digest
from math import isfinite
from typing import Any
from zoneinfo import ZoneInfo

from openpool import __version__, db
from openpool.chemistry.acid_base import dose_muriatic_acid_for_ph, dose_soda_ash_for_ph
from openpool.chemistry.alkalinity import dose_baking_soda_for_ta
from openpool.chemistry.calcium import dose_calcium_chloride_for_ch
from openpool.chemistry.chlorine import (
    CAL_HYPO_DEFAULT_PERCENT,
    CHLORINE_ADDITION_CHEMICALS,
    dose_dry_chlorine_for_fc,
    dose_liquid_chlorine_for_fc,
    validate_chlorine_strength,
)
from openpool.chemistry.cya import dose_dry_stabilizer_for_cya
from openpool.chemistry.operations import estimate_drain_for_dilution, estimate_swg_runtime
from openpool.chemistry.salt import dose_salt_for_ppm
from openpool.chemistry.targets import fc_cya_targets

# Typical balanced ranges used only to give an at-a-glance status hint on the
# dashboard. These are general pool-care comfort ranges, not precise targets;
# FC and CYA use the dedicated target logic instead.
TYPICAL_RANGES: dict[str, tuple[float | None, float | None]] = {
    "cc": (None, 0.5),
    "ph": (7.2, 7.8),
    "ta": (60, 120),
    "ch": (250, 650),
    "csi": (-0.3, 0.3),
}
FRESH_READING_MAX_AGE = timedelta(hours=12)
GOAL_VALUE_BOUNDS: dict[str, tuple[float, float]] = {
    "raise_fc": (0, 100),
    "slam_fc": (0, 100),
    "raise_cya": (0, 500),
    "raise_salt": (0, 50_000),
    "raise_ch": (0, 2_000),
    "raise_ta": (0, 2_000),
    "lower_ph": (0, 14),
    "raise_ph": (0, 14),
    "lower_by_dilution": (0, 50_000),
    "swg_runtime": (0, 100),
}
CALCULATION_INPUT_BOUNDS: dict[str, tuple[float, float]] = {
    "strength": (1, 100),
    "ta": (0, 2_000),
    "cya": (0, 500),
    "borates": (0, 200),
}


def humanize_number(value: Any, grouping: bool = True) -> str:
    """Format a numeric value for display: drop a trailing ``.0`` and, by
    default, add thousands separators. ``None`` becomes an empty string so the
    same filter is safe for form inputs."""
    if value is None:
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number == int(number):
        whole = int(number)
        return f"{whole:,}" if grouping else str(whole)
    if number != 0 and round(number, 2) == 0:
        return f"{number:.2g}"
    formatted = f"{number:,.2f}" if grouping else f"{number:.2f}"
    return formatted.rstrip("0").rstrip(".")


def _classify(value: float | None, low: float | None, high: float | None) -> str:
    if value is None or (low is None and high is None):
        return "none"
    if low is not None and value < low:
        return "low"
    if high is not None and value > high:
        return "high"
    return "ok"


def _range_text(low: float | None, high: float | None) -> str | None:
    if low is not None and high is not None:
        return f"{low:g}-{high:g}"
    if high is not None:
        return f"<= {high:g}"
    if low is not None:
        return f">= {low:g}"
    return None


def reading_tiles(
    reading: dict[str, Any] | None,
    targets: Any,
    sanitizer: str,
) -> list[dict[str, Any]]:
    """Build dashboard/share status tiles with target context per metric."""

    def value(key: str) -> float | None:
        return reading.get(key) if reading else None

    normalized_sanitizer = sanitizer.lower()
    if normalized_sanitizer in {"swg", "salt_water_generator"}:
        cya_low, cya_high = 60, 80
        salt_low, salt_high = 2700, 3400
    elif normalized_sanitizer == "liquid_chlorine":
        cya_low, cya_high = 30, 60
        salt_low, salt_high = None, None
    else:
        cya_low, cya_high = None, None
        salt_low, salt_high = None, None

    # "target" ranges come from sanitizer-specific recommendations (FC/CYA
    # chart, SWG salt window); everything else is a generic comfort range and
    # is labeled "typical" so the dashboard does not overstate precision.
    fc_low = targets.target_low if targets else None
    fc_high = targets.target_high if targets else None
    specs = [
        ("fc", "FC", "ppm", value("fc"), fc_low, fc_high, "target"),
        ("cc", "CC", "ppm", value("cc"), *TYPICAL_RANGES["cc"], "typical"),
        ("ph", "pH", "", value("ph"), *TYPICAL_RANGES["ph"], "typical"),
        ("ta", "TA", "ppm", value("ta"), *TYPICAL_RANGES["ta"], "typical"),
        ("ch", "CH", "ppm", value("ch"), *TYPICAL_RANGES["ch"], "typical"),
        ("cya", "CYA", "ppm", value("cya"), cya_low, cya_high, "target"),
        ("salt", "Salt", "ppm", value("salt"), salt_low, salt_high, "target"),
        ("csi", "CSI", "", value("csi"), *TYPICAL_RANGES["csi"], "typical"),
    ]
    return [
        {
            "key": key,
            "label": label,
            "unit": unit,
            "value": val,
            "state": _classify(val, low, high),
            "range": _range_text(low, high),
            "range_kind": kind,
        }
        for key, label, unit, val, low, high, kind in specs
    ]


def _overview(reading: dict[str, Any] | None, include_notes: bool = False) -> dict[str, Any] | None:
    if not reading:
        return None
    overview = {
        "fc": reading.get("fc"),
        "cc": reading.get("cc"),
        "tc": reading.get("tc"),
        "ph": reading.get("ph"),
        "ta": reading.get("ta"),
        "ch": reading.get("ch"),
        "cya": reading.get("cya"),
        "salt": reading.get("salt"),
        "borates": reading.get("borates"),
        "waterTemp": reading.get("water_temp_f"),
        "filterPressure": reading.get("filter_pressure"),
        "csi": reading.get("csi"),
        "csiMeta": reading.get("csi_meta"),
        "testedAt": reading.get("tested_at"),
    }
    if include_notes:
        overview["notes"] = reading.get("notes")
    return overview


SUPPORTED_GOALS = (
    "raise_fc",
    "slam_fc",
    "raise_cya",
    "raise_salt",
    "raise_ch",
    "raise_ta",
    "lower_ph",
    "raise_ph",
    "lower_by_dilution",
    "swg_runtime",
)


def _require(values: dict[str, Any], goal: str, *names: str) -> None:
    missing = [name for name in names if values.get(name) is None]
    if missing:
        raise ValueError(f"{goal} needs: {', '.join(missing)}")


def _value_or_default(values: dict[str, Any], name: str, default: Any) -> Any:
    value = values.get(name)
    return default if value is None else value


def _validate_calculation_inputs(values: dict[str, Any]) -> None:
    for name, (low, high) in CALCULATION_INPUT_BOUNDS.items():
        value = values.get(name)
        if value is not None and not low <= float(value) <= high:
            raise ValueError(f"{name} must be between {low:g} and {high:g}")

    cell_lbs_per_day = values.get("cell_lbs_per_day")
    if cell_lbs_per_day is not None and float(cell_lbs_per_day) <= 0:
        raise ValueError("cell_lbs_per_day must be greater than 0")

    pump_hours = values.get("pump_hours")
    if pump_hours is not None and not 0 < float(pump_hours) <= 24:
        raise ValueError("pump_hours must be greater than 0 and at most 24")


def calculator_product(goal: str, product: str | None) -> str | None:
    if goal == "raise_fc":
        return product or "liquid_chlorine"
    return {"slam_fc": "liquid_chlorine", "lower_ph": "muriatic_acid"}.get(goal)


def calculator_strength_defaults(pool: dict[str, Any]) -> dict[str, float]:
    return {
        "liquid_chlorine": pool["default_chlorine_percent"],
        "cal_hypo": CAL_HYPO_DEFAULT_PERCENT,
        "muriatic_acid": 31.45,
    }


def _confirmed_calculator_strength(goal: str, values: dict[str, Any]) -> float:
    product = calculator_product(goal, values.get("product"))
    if goal != "raise_fc" and values.get("product") not in (None, "", product):
        raise ValueError(f"{goal} uses {product}; select and confirm its label strength")
    _require(values, goal, "strength")
    strength = float(values["strength"])
    if product in {"liquid_chlorine", "cal_hypo"}:
        validate_chlorine_strength(product, strength)
    if values.get("strength_confirmed") is not True or values.get("strength_product") != product:
        raise ValueError(f"Confirm the label strength for {product} before calculating")
    return strength


def calculate_goal(pool: dict[str, Any], goal: str, values: dict[str, Any]) -> dict[str, Any]:
    pool_gallons = float(_value_or_default(values, "pool_gallons", pool["volume_gallons"]))
    numeric_values = {"pool_gallons": pool_gallons}
    numeric_values.update(
        {
            name: float(value)
            for name, value in values.items()
            if name not in {"goal", "product", "strength_confirmed", "strength_product"}
            and value is not None
        }
    )
    for name, value in numeric_values.items():
        if not isfinite(value):
            raise ValueError(f"{name} must be a finite number")
    if not 0 < pool_gallons <= 1_000_000:
        raise ValueError("pool_gallons must be greater than 0 and at most 1000000")
    if goal not in GOAL_VALUE_BOUNDS:
        raise ValueError(f"supported goals are {', '.join(SUPPORTED_GOALS)}")
    _validate_calculation_inputs(values)
    low, high = GOAL_VALUE_BOUNDS[goal]
    for name in ("current", "target"):
        value = values.get(name)
        if value is not None and not low <= float(value) <= high:
            raise ValueError(f"{name} for {goal} must be between {low:g} and {high:g}")
    extra: dict[str, Any] = {}

    if goal == "raise_fc":
        _require(values, goal, "current", "target")
        product = values.get("product") or "liquid_chlorine"
        strength = (
            _confirmed_calculator_strength(goal, values)
            if product in {"liquid_chlorine", "cal_hypo"}
            else None
        )
        if product == "liquid_chlorine":
            dose = dose_liquid_chlorine_for_fc(
                pool_gallons=pool_gallons,
                current_fc=float(values["current"]),
                target_fc=float(values["target"]),
                chlorine_percent=strength,
                jug_size_fl_oz=float(_value_or_default(pool, "jug_size_fl_oz", 128.0)),
            )
        else:
            dose = dose_dry_chlorine_for_fc(
                pool_gallons=pool_gallons,
                current_fc=float(values["current"]),
                target_fc=float(values["target"]),
                product=product,
                available_chlorine_percent=strength,
            )
        if strength is not None:
            extra["strengthPercent"] = strength
    elif goal == "slam_fc":
        _require(values, goal, "current")
        targets = fc_cya_targets(
            values.get("cya"), _value_or_default(pool, "sanitizer", "liquid_chlorine")
        )
        dose = dose_liquid_chlorine_for_fc(
            pool_gallons=pool_gallons,
            current_fc=float(values["current"]),
            target_fc=targets.slam,
            chlorine_percent=_confirmed_calculator_strength(goal, values),
            jug_size_fl_oz=float(_value_or_default(pool, "jug_size_fl_oz", 128.0)),
        )
        dose.warnings.extend(targets.warnings)
        dose.warnings.extend(
            [
                "SLAM is a process: hold FC at the shock level, test and re-dose "
                "every few hours until the water passes.",
                "Done when CC is under 0.5, overnight FC loss is under 1 ppm, "
                "and the water is clear.",
            ]
        )
        extra["targets"] = targets.to_dict()
        extra["targetFc"] = targets.slam
        extra["strengthPercent"] = float(values["strength"])
    elif goal == "raise_cya":
        _require(values, goal, "current", "target")
        dose = dose_dry_stabilizer_for_cya(
            pool_gallons=pool_gallons,
            current_cya=float(values["current"]),
            target_cya=float(values["target"]),
        )
    elif goal == "raise_salt":
        _require(values, goal, "current", "target")
        dose = dose_salt_for_ppm(
            pool_gallons=pool_gallons,
            current_salt=float(values["current"]),
            target_salt=float(values["target"]),
            bag_size_lbs=float(_value_or_default(pool, "bag_size_lbs", 40.0)),
        )
    elif goal == "raise_ch":
        _require(values, goal, "current", "target")
        dose = dose_calcium_chloride_for_ch(
            pool_gallons=pool_gallons,
            current_ch=float(values["current"]),
            target_ch=float(values["target"]),
        )
    elif goal == "raise_ta":
        _require(values, goal, "current", "target")
        dose = dose_baking_soda_for_ta(
            pool_gallons=pool_gallons,
            current_ta=float(values["current"]),
            target_ta=float(values["target"]),
        )
    elif goal == "lower_ph":
        _require(values, goal, "current", "target", "ta")
        dose = dose_muriatic_acid_for_ph(
            pool_gallons=pool_gallons,
            current_ph=float(values["current"]),
            target_ph=float(values["target"]),
            ta=float(values["ta"]),
            cya=values.get("cya"),
            borates=values.get("borates"),
            acid_percent=_confirmed_calculator_strength(goal, values),
        )
        extra["strengthPercent"] = float(values["strength"])
    elif goal == "raise_ph":
        _require(values, goal, "current", "target", "ta")
        dose = dose_soda_ash_for_ph(
            pool_gallons=pool_gallons,
            current_ph=float(values["current"]),
            target_ph=float(values["target"]),
            ta=float(values["ta"]),
            cya=values.get("cya"),
            borates=values.get("borates"),
        )
    elif goal == "lower_by_dilution":
        _require(values, goal, "current", "target")
        dose = estimate_drain_for_dilution(
            pool_gallons=pool_gallons,
            current_ppm=float(values["current"]),
            target_ppm=float(values["target"]),
        )
    elif goal == "swg_runtime":
        _require(values, goal, "target", "cell_lbs_per_day")
        dose = estimate_swg_runtime(
            pool_gallons=pool_gallons,
            cell_lbs_per_day=float(values["cell_lbs_per_day"]),
            target_fc_per_day=float(values["target"]),
            pump_hours_per_day=float(_value_or_default(values, "pump_hours", 24.0)),
        )
    else:
        raise ValueError(f"supported goals are {', '.join(SUPPORTED_GOALS)}")

    return {"goal": goal, "poolGallons": pool_gallons, "dose": dose.to_dict(), **extra}


def share_access_allowed(pool: dict[str, Any], token: str | None) -> bool:
    if not pool.get("share_enabled"):
        return False
    expected = pool.get("share_token")
    if not expected:
        return False
    return token is not None and compare_digest(str(token), str(expected))


def recommended_actions(
    pool: dict[str, Any],
    reading: dict[str, Any] | None,
    additions: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    if not reading:
        return []
    if reading.get("fc") is None:
        return [_retest_action("The latest reading has no FC value. Retest before dosing.")]

    try:
        targets = fc_cya_targets(
            reading.get("cya"), _value_or_default(pool, "sanitizer", "liquid_chlorine")
        )
    except ValueError as exc:
        return [_retest_action(str(exc))]

    current_fc = float(reading["fc"])
    block_reason = _recommendation_block_reason(pool, reading, additions or [], now)
    if block_reason:
        return [_retest_action(block_reason)]
    if current_fc >= targets.target_low:
        return []

    target_fc = targets.target_high
    try:
        validate_chlorine_strength(
            "liquid_chlorine", float(_value_or_default(pool, "default_chlorine_percent", 10.0))
        )
    except ValueError as exc:
        return [_retest_action(str(exc))]
    dose = dose_liquid_chlorine_for_fc(
        pool_gallons=float(pool["volume_gallons"]),
        current_fc=current_fc,
        target_fc=target_fc,
        chlorine_percent=float(
            _value_or_default(pool, "default_chlorine_percent", 10.0)
        ),
        jug_size_fl_oz=float(_value_or_default(pool, "jug_size_fl_oz", 128.0)),
    )
    dose.warnings.extend(targets.warnings)
    severity = "danger" if current_fc < targets.minimum else "caution"
    why = (
        f"FC is {current_fc:g} ppm. With CYA rounded to {targets.cya:g}, "
        "the maintenance target range is "
        f"{targets.target_low:g}-{targets.target_high:g} ppm."
    )
    if targets.warnings:
        why = f"{' '.join(targets.warnings)} {why}"
    return [
        {
            "kind": "chlorine",
            "severity": severity,
            "title": "Add liquid chlorine",
            "summary": f"Add about {dose.amount:g} {dose.unit.replace('_', ' ')}.",
            "targetFc": target_fc,
            "dose": dose.to_dict(),
            "why": why,
        }
    ]


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _retest_action(reason: str) -> dict[str, Any]:
    return {
        "kind": "retest",
        "severity": "retest",
        "title": "Retest before dosing",
        "summary": "No chemical dose is calculated.",
        "why": reason,
    }


def _recommendation_block_reason(
    pool: dict[str, Any],
    reading: dict[str, Any],
    additions: list[dict[str, Any]],
    now: datetime | None,
) -> str | None:
    tested_at = _parse_timestamp(reading.get("tested_at"))
    if tested_at is None:
        return "The latest reading has no valid timestamp. Retest before calculating a dose."

    current_time = now or datetime.now(UTC)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=UTC)
    current_time = current_time.astimezone(UTC)
    age = current_time - tested_at
    if age < timedelta(0):
        return "The latest reading timestamp is in the future. Retest before calculating a dose."

    timezone_name = pool.get("timezone") or "UTC"
    timezone = ZoneInfo(str(timezone_name))
    if age > FRESH_READING_MAX_AGE:
        return "The latest reading is more than 12 hours old. Retest before calculating a dose."
    if tested_at.astimezone(timezone).date() != current_time.astimezone(timezone).date():
        return "The latest reading is not from today in the pool timezone. Retest before dosing."

    for addition in additions:
        if addition.get("chemical") not in CHLORINE_ADDITION_CHEMICALS:
            continue
        added_at = _parse_timestamp(addition.get("added_at"))
        if added_at is None:
            return (
                "A chlorine addition has no valid timestamp. "
                "Retest before calculating another dose."
            )
        if added_at >= tested_at:
            return (
                "Chlorine was logged after the latest reading. "
                "Retest before calculating another dose."
            )
    return None


def status_summary(
    pool: dict[str, Any],
    reading: dict[str, Any] | None,
    additions: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> dict[str, str]:
    if not reading:
        return {"level": "empty", "text": "No readings yet"}

    actions = recommended_actions(pool, reading, additions, now)
    needs_retest = any(action["severity"] == "retest" for action in actions)
    if needs_retest:
        return {"level": "caution", "text": "Retest before dosing"}
    if any(action["severity"] == "danger" for action in actions):
        return {"level": "danger", "text": "Act now - low FC"}

    try:
        targets = fc_cya_targets(
            reading.get("cya"), _value_or_default(pool, "sanitizer", "liquid_chlorine")
        )
    except ValueError:
        targets = None
    tiles = reading_tiles(
        reading,
        targets,
        _value_or_default(pool, "sanitizer", "liquid_chlorine"),
    )
    outside_count = sum(tile["state"] in {"low", "high"} for tile in tiles)
    if outside_count:
        reading_text = "reading" if outside_count == 1 else "readings"
        return {"level": "caution", "text": f"{outside_count} {reading_text} outside range"}

    return {"level": "good", "text": "All readings in range"}


def build_snapshot(conn: db.Connection, pool_id: str) -> dict[str, Any]:
    pool = db.get_pool(conn, pool_id)
    if not pool:
        raise KeyError(pool_id)

    latest = db.latest_reading(conn, pool_id)
    additions = db.list_additions(conn, pool_id, limit=3)
    recommendation_additions = db.list_additions(
        conn,
        pool_id,
        limit=10_000,
        start_utc=latest.get("tested_at") if latest else None,
    )
    timezone_name = pool.get("timezone") or "UTC"
    target_error = None
    try:
        targets = fc_cya_targets(
            latest.get("cya") if latest else pool.get("default_cya_target"),
            _value_or_default(pool, "sanitizer", "liquid_chlorine"),
        )
    except ValueError as exc:
        targets = None
        target_error = str(exc)

    overview = _overview(latest, include_notes=bool(pool.get("include_notes_in_share")))
    if overview:
        overview["testedAtLocal"] = db.local_timestamp(
            latest.get("tested_at"),
            timezone_name,
        )

    return {
        "app": "openpool",
        "version": __version__,
        "pool": {
            "id": pool["id"],
            "name": pool["name"],
            "volumeGallons": pool["volume_gallons"],
            "surface": pool["surface"],
            "sanitizer": pool["sanitizer"],
            "unitSystem": pool["unit_system"],
            "timezone": pool["timezone"],
        },
        "status": status_summary(pool, latest, recommendation_additions),
        "overview": overview,
        "tiles": reading_tiles(
            latest,
            targets,
            _value_or_default(pool, "sanitizer", "liquid_chlorine"),
        ),
        "targets": targets.to_dict() if targets else {"error": target_error},
        "recommendations": recommended_actions(pool, latest, recommendation_additions),
        "recentAdditions": [
            {
                "chemical": item["chemical"],
                "amount": item["amount"],
                "unit": item["unit"],
                "addedAt": item["added_at"],
                "addedAtLocal": db.local_timestamp(item.get("added_at"), timezone_name),
                "reason": item.get("reason"),
            }
            for item in additions
        ],
    }
