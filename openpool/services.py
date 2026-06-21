from __future__ import annotations

from hmac import compare_digest
from typing import Any

from openpool import __version__, db
from openpool.chemistry.acid_base import dose_muriatic_acid_for_ph, dose_soda_ash_for_ph
from openpool.chemistry.alkalinity import dose_baking_soda_for_ta
from openpool.chemistry.calcium import dose_calcium_chloride_for_ch
from openpool.chemistry.chlorine import dose_dry_chlorine_for_fc, dose_liquid_chlorine_for_fc
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

    is_swg = sanitizer.lower() in {"swg", "salt_water_generator"}
    cya_low, cya_high = (60, 80) if is_swg else (30, 60)
    salt_low, salt_high = (2700, 3400) if is_swg else (None, None)

    # "target" ranges come from sanitizer-specific recommendations (FC/CYA
    # chart, SWG salt window); everything else is a generic comfort range and
    # is labeled "typical" so the dashboard does not overstate precision.
    specs = [
        ("fc", "FC", "ppm", value("fc"), targets.target_low, targets.target_high, "target"),
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


def calculate_goal(pool: dict[str, Any], goal: str, values: dict[str, Any]) -> dict[str, Any]:
    pool_gallons = float(values.get("pool_gallons") or pool["volume_gallons"])
    extra: dict[str, Any] = {}

    if goal == "raise_fc":
        _require(values, goal, "current", "target")
        product = values.get("product") or "liquid_chlorine"
        if product == "liquid_chlorine":
            dose = dose_liquid_chlorine_for_fc(
                pool_gallons=pool_gallons,
                current_fc=float(values["current"]),
                target_fc=float(values["target"]),
                chlorine_percent=float(
                    values.get("strength") or pool["default_chlorine_percent"]
                ),
                jug_size_fl_oz=float(pool.get("jug_size_fl_oz") or 128.0),
            )
        else:
            dose = dose_dry_chlorine_for_fc(
                pool_gallons=pool_gallons,
                current_fc=float(values["current"]),
                target_fc=float(values["target"]),
                product=product,
                available_chlorine_percent=(
                    float(values["strength"])
                    if product == "cal_hypo" and values.get("strength")
                    else None
                ),
            )
    elif goal == "slam_fc":
        _require(values, goal, "current")
        targets = fc_cya_targets(values.get("cya"), pool.get("sanitizer") or "liquid_chlorine")
        dose = dose_liquid_chlorine_for_fc(
            pool_gallons=pool_gallons,
            current_fc=float(values["current"]),
            target_fc=targets.slam,
            chlorine_percent=float(values.get("strength") or pool["default_chlorine_percent"]),
            jug_size_fl_oz=float(pool.get("jug_size_fl_oz") or 128.0),
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
            bag_size_lbs=float(pool.get("bag_size_lbs") or 40.0),
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
        )
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
            pump_hours_per_day=float(values.get("pump_hours") or 24.0),
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
) -> list[dict[str, Any]]:
    if not reading or reading.get("fc") is None:
        return []

    targets = fc_cya_targets(reading.get("cya"), pool.get("sanitizer") or "liquid_chlorine")
    current_fc = float(reading["fc"])
    if current_fc >= targets.target_low:
        return []

    target_fc = targets.target_high
    dose = dose_liquid_chlorine_for_fc(
        pool_gallons=float(pool["volume_gallons"]),
        current_fc=current_fc,
        target_fc=target_fc,
        chlorine_percent=float(pool.get("default_chlorine_percent") or 10.0),
        jug_size_fl_oz=float(pool.get("jug_size_fl_oz") or 128.0),
    )
    severity = "danger" if current_fc < targets.minimum else "caution"
    return [
        {
            "kind": "chlorine",
            "severity": severity,
            "title": "Add liquid chlorine",
            "summary": f"Add about {dose.amount:g} {dose.unit.replace('_', ' ')}.",
            "targetFc": target_fc,
            "dose": dose.to_dict(),
            "why": (
                f"FC is {current_fc:g} ppm. With CYA rounded to {targets.cya:g}, "
                "the maintenance target range is "
                f"{targets.target_low:g}-{targets.target_high:g} ppm."
            ),
        }
    ]


def status_summary(pool: dict[str, Any], reading: dict[str, Any] | None) -> dict[str, str]:
    if not reading:
        return {"level": "empty", "text": "No readings yet"}
    actions = recommended_actions(pool, reading)
    if not actions:
        return {"level": "good", "text": "Balanced - no action needed"}
    if any(action["severity"] == "danger" for action in actions):
        return {"level": "danger", "text": "Act now - low FC"}
    return {"level": "caution", "text": "Add chlorine today"}


def build_snapshot(conn: db.Connection, pool_id: str) -> dict[str, Any]:
    pool = db.get_pool(conn, pool_id)
    if not pool:
        raise KeyError(pool_id)

    latest = db.latest_reading(conn, pool_id)
    additions = db.list_additions(conn, pool_id, limit=3)
    timezone_name = pool.get("timezone") or "UTC"
    targets = fc_cya_targets(
        latest.get("cya") if latest else pool.get("default_cya_target"),
        pool.get("sanitizer") or "liquid_chlorine",
    )

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
        "status": status_summary(pool, latest),
        "overview": overview,
        "tiles": reading_tiles(latest, targets, pool.get("sanitizer") or "liquid_chlorine"),
        "targets": targets.to_dict(),
        "recommendations": recommended_actions(pool, latest),
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
