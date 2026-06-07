from __future__ import annotations

import pytest

from openpool import db, services
from openpool.schemas import ReadingIn


def test_reading_persists_and_computes_tc(conn):
    reading = db.create_reading(
        conn,
        "example",
        {
            "tested_at": "2026-06-07T09:15",
            "fc": 3,
            "cc": 0.5,
            "ph": 7.6,
            "cya": 40,
            "notes": "private note",
        },
    )
    latest = db.latest_reading(conn, "example")
    assert latest["id"] == reading["id"]
    assert latest["tc"] == 3.5
    # America/Phoenix is UTC-7; 09:15 local becomes 16:15 UTC.
    assert latest["tested_at"] == "2026-06-07T16:15:00Z"


def test_share_payload_excludes_notes_by_default(conn):
    db.create_reading(
        conn,
        "example",
        {"fc": 1, "cc": 0, "ph": 7.5, "cya": 40, "notes": "do not leak"},
    )
    db.update_pool(
        conn,
        "example",
        {"share_enabled": 1, "share_token": "read-only-token-123"},
    )
    db.create_addition(
        conn,
        "example",
        {
            "added_at": "2026-06-07T10:35",
            "chemical": "liquid_chlorine",
            "amount": 153.6,
            "unit": "fl_oz",
        },
    )
    pool = db.get_pool(conn, "example")
    snapshot = services.build_snapshot(conn, "example")

    assert services.share_access_allowed(pool, "read-only-token-123")
    assert not services.share_access_allowed(pool, "wrong")
    assert "notes" not in snapshot["overview"]
    assert snapshot["recommendations"][0]["kind"] == "chlorine"
    assert snapshot["recentAdditions"][0]["addedAtLocal"] == "2026-06-07T10:35:00-07:00"


def test_public_pool_hides_token_and_notes(conn):
    db.update_pool(conn, "example", {"share_enabled": 1, "notes": "secret place"})
    pool = db.get_pool(conn, "example")
    safe = db.public_pool(pool)
    assert "share_token" not in safe
    assert "notes" not in safe


def test_share_token_generated_when_enabled_without_one(conn):
    updated = db.update_pool(conn, "example", {"share_enabled": 1})
    assert len(updated["share_token"]) >= 16
    assert services.share_access_allowed(updated, updated["share_token"])
    assert not services.share_access_allowed(updated, None)


def test_invalid_pool_id_rejected(conn):
    with pytest.raises(ValueError):
        db.get_pool(conn, "../nope")


def test_reading_schema_rejects_impossible_values():
    with pytest.raises(ValueError):
        ReadingIn(fc=-1, ph=20)


def test_default_pool_uses_configured_timezone(conn):
    pool = db.get_pool(conn, "example")
    assert pool["timezone"] == "America/Phoenix"


def test_reading_tiles_classify_against_targets(conn):
    from openpool.chemistry.targets import fc_cya_targets

    reading = {"fc": 1, "cc": 0.6, "ph": 8.0, "ta": 70, "cya": 40, "salt": 3000}
    targets = fc_cya_targets(40, "liquid_chlorine")
    tiles = {t["key"]: t for t in services.reading_tiles(reading, targets, "liquid_chlorine")}

    assert tiles["fc"]["state"] == "low"
    assert tiles["fc"]["range"] == "5-7"
    assert tiles["cc"]["state"] == "high"
    assert tiles["ph"]["state"] == "high"
    assert tiles["ta"]["state"] == "ok"
    assert tiles["cya"]["state"] == "ok"
    # Salt has no target band on a liquid-chlorine pool: neutral, not "ok".
    assert tiles["salt"]["state"] == "none"
    assert tiles["csi"]["state"] == "none"


def test_status_summary_levels(conn):
    pool = db.get_pool(conn, "example")
    assert services.status_summary(pool, None)["level"] == "empty"

    db.create_reading(conn, "example", {"tested_at": "2026-06-01T08:00", "fc": 0.5, "cya": 40})
    low = db.latest_reading(conn, "example")
    assert services.status_summary(pool, low)["level"] == "danger"

    db.create_reading(conn, "example", {"tested_at": "2026-06-02T08:00", "fc": 6, "cya": 40})
    good = db.latest_reading(conn, "example")
    assert services.status_summary(pool, good)["level"] == "good"
