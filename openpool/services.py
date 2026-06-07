from __future__ import annotations

import sqlite3
from hmac import compare_digest
from typing import Any

from openpool import __version__
from openpool import db
from openpool.chemistry.chlorine import dose_liquid_chlorine_for_fc
from openpool.chemistry.cya import dose_dry_stabilizer_for_cya
from openpool.chemistry.salt import dose_salt_for_ppm
from openpool.chemistry.targets import fc_cya_targets


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


def calculate_goal(pool: dict[str, Any], goal: str, values: dict[str, Any]) -> dict[str, Any]:
    pool_gallons = float(values.get("pool_gallons") or pool["volume_gallons"])

    if goal == "raise_fc":
        dose = dose_liquid_chlorine_for_fc(
            pool_gallons=pool_gallons,
            current_fc=float(values["current"]),
            target_fc=float(values["target"]),
            chlorine_percent=float(values.get("strength") or pool["default_chlorine_percent"]),
            jug_size_fl_oz=float(pool.get("jug_size_fl_oz") or 128.0),
        )
    elif goal == "raise_cya":
        dose = dose_dry_stabilizer_for_cya(
            pool_gallons=pool_gallons,
            current_cya=float(values["current"]),
            target_cya=float(values["target"]),
        )
    elif goal == "raise_salt":
        dose = dose_salt_for_ppm(
            pool_gallons=pool_gallons,
            current_salt=float(values["current"]),
            target_salt=float(values["target"]),
            bag_size_lbs=float(pool.get("bag_size_lbs") or 40.0),
        )
    else:
        raise ValueError("supported goals are raise_fc, raise_cya, and raise_salt")

    return {"goal": goal, "poolGallons": pool_gallons, "dose": dose.to_dict()}


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


def build_snapshot(conn: sqlite3.Connection, pool_id: str) -> dict[str, Any]:
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
