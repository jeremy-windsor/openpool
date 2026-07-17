from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from openpool import db, services
from openpool.schemas import AdditionIn, CalculationIn, PoolIn, ReadingIn, validate_model


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
    assert latest["csi_meta"]["formula_version"] == db.CSI_FORMULA_VERSION
    assert "warnings" in latest["csi_meta"]
    # America/Phoenix is UTC-7; 09:15 local becomes 16:15 UTC.
    assert latest["tested_at"] == "2026-06-07T16:15:00Z"


@pytest.mark.parametrize("tested_at", ["garbageZ", "2026-99-99T00:00Z"])
def test_bad_z_timestamp_rejected_by_db(conn, tested_at):
    with pytest.raises(ValueError, match="invalid timestamp"):
        db.create_reading(conn, "example", {"tested_at": tested_at, "fc": 3})


def test_z_timestamp_round_trips_canonically(conn):
    reading = db.create_reading(
        conn,
        "example",
        {"tested_at": "2026-06-01T12:00:00Z", "fc": 3},
    )

    assert reading["tested_at"] == "2026-06-01T12:00:00Z"


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


def test_share_token_preserved_when_enabled_with_existing_token(conn):
    db.update_pool(conn, "example", {"share_token": "read-only-token-123"})

    enabled = db.update_pool(conn, "example", {"share_enabled": 1})
    renamed = db.update_pool(conn, "example", {"share_enabled": 1, "name": "Renamed Pool"})

    assert enabled["share_token"] == "read-only-token-123"
    assert renamed["share_token"] == "read-only-token-123"
    assert renamed["name"] == "Renamed Pool"


def test_legacy_short_share_token_cannot_be_enabled(conn):
    conn.execute(
        "update pool_profiles set share_token = 'short' where id = 'example'"
    )
    conn.commit()

    with pytest.raises(ValueError, match="at least 16 characters"):
        db.update_pool(conn, "example", {"share_enabled": 1})

    assert db.get_pool(conn, "example")["share_enabled"] == 0


def test_create_pool_preserves_explicit_zero_targets(conn):
    pool = db.create_pool(
        conn,
        {
            "id": "zero-targets",
            "volume_gallons": 10_000,
            "default_cya_target": 0,
            "default_salt_target": 0,
        },
    )

    assert pool["default_cya_target"] == 0
    assert pool["default_salt_target"] == 0


def test_duplicate_pool_raises_domain_error(conn):
    with pytest.raises(db.PoolAlreadyExistsError, match="already exists"):
        db.create_pool(conn, {"id": "example", "volume_gallons": 10_000})


def test_duplicate_pool_insert_race_raises_domain_error(conn, monkeypatch):
    monkeypatch.setattr(db, "get_pool", lambda _conn, _pool_id: None)

    with pytest.raises(db.PoolAlreadyExistsError, match="already exists"):
        db.create_pool(conn, {"id": "example", "volume_gallons": 10_000})

    conn.rollback()


def test_invalid_pool_id_rejected(conn):
    with pytest.raises(ValueError):
        db.get_pool(conn, "../nope")


def test_reading_schema_rejects_impossible_values():
    with pytest.raises(ValueError):
        ReadingIn(fc=-1, ph=20)


@pytest.mark.parametrize(
    "model_class, base, field, valid_low, valid_high, invalid_low, invalid_high",
    [
        (ReadingIn, {}, "fc", 0, 100, -1, 101),
        (ReadingIn, {}, "cc", 0, 100, -1, 101),
        (ReadingIn, {}, "ph", 0, 14, -1, 15),
        (ReadingIn, {}, "ta", 0, 2_000, -1, 2_001),
        (ReadingIn, {}, "ch", 0, 2_000, -1, 2_001),
        (ReadingIn, {}, "cya", 0, 500, -1, 501),
        (ReadingIn, {}, "salt", 0, 50_000, -1, 50_001),
        (ReadingIn, {}, "borates", 0, 200, -1, 201),
        (ReadingIn, {}, "water_temp_f", 32, 120, 31, 121),
        (ReadingIn, {}, "filter_pressure", 0, 100, -1, 101),
        (PoolIn, {}, "volume_gallons", 1, 1_000_000, 0, 1_000_001),
        (PoolIn, {}, "spa_volume_gallons", 1, 1_000_000, 0, 1_000_001),
        (PoolIn, {}, "default_chlorine_percent", 1, 100, 0.5, 101),
        (PoolIn, {}, "default_cya_target", 0, 500, -1, 501),
        (PoolIn, {}, "default_salt_target", 0, 50_000, -1, 50_001),
        (
            AdditionIn,
            {"chemical": "salt", "amount": 1, "unit": "lb"},
            "strength_percent",
            1,
            100,
            0.5,
            101,
        ),
        (
            AdditionIn,
            {"chemical": "salt", "amount": 1, "unit": "lb"},
            "amount",
            1,
            100_000,
            0,
            100_001,
        ),
        (CalculationIn, {"goal": "raise_fc"}, "pool_gallons", 1, 1_000_000, 0, 1_000_001),
        (CalculationIn, {"goal": "raise_fc"}, "strength", 1, 100, 0.5, 101),
        (CalculationIn, {"goal": "lower_ph"}, "ta", 0, 2_000, -1, 2_001),
        (CalculationIn, {"goal": "slam_fc"}, "cya", 0, 500, -1, 501),
        (CalculationIn, {"goal": "lower_ph"}, "borates", 0, 200, -1, 201),
    ],
)
def test_documented_hard_bound_edges(
    model_class, base, field, valid_low, valid_high, invalid_low, invalid_high
):
    validate_model(model_class, {**base, field: valid_low})
    validate_model(model_class, {**base, field: valid_high})
    for invalid in (invalid_low, invalid_high):
        with pytest.raises(ValueError, match=field):
            validate_model(model_class, {**base, field: invalid})


def test_client_cannot_supply_server_owned_reading_values():
    with pytest.raises(ValueError):
        ReadingIn(fc=3, cc=0.5, tc=99)
    with pytest.raises(ValueError):
        ReadingIn(fc=3, csi=99)


def test_db_ignores_server_owned_reading_values(conn):
    reading = db.create_reading(conn, "example", {"fc": 3, "cc": 0.5, "tc": 99, "csi": 99})

    assert reading["tc"] == 3.5
    assert reading["csi"] is None


def test_linked_reading_must_belong_to_same_pool(conn):
    db.create_pool(conn, {"id": "other", "volume_gallons": 10_000})
    reading = db.create_reading(conn, "other", {"fc": 3})

    with pytest.raises(ValueError, match="same pool"):
        db.create_addition(
            conn,
            "example",
            {
                "chemical": "liquid_chlorine",
                "amount": 10,
                "unit": "fl_oz",
                "linked_reading_id": reading["id"],
            },
        )


def test_database_rejects_cross_pool_link_and_out_of_bounds_values(conn):
    db.create_pool(conn, {"id": "other", "volume_gallons": 10_000})
    reading = db.create_reading(conn, "other", {"fc": 3})

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            insert into chemical_additions (
              id, pool_id, added_at, chemical, amount, unit, linked_reading_id, created_at
            ) values ('bad-link', 'example', '2026-01-01Z', 'salt', 1, 'lb', ?, '2026-01-01Z')
            """,
            (reading["id"],),
        )
    conn.rollback()


def test_schema_copier_and_export_columns_share_one_contract(conn):
    from openpool import migrate

    assert dict(migrate.TABLES) == db.TABLE_COLUMNS
    for table, expected in db.TABLE_COLUMNS.items():
        actual = tuple(
            row["name"] for row in conn.execute(f"pragma table_info({table})").fetchall()
        )
        assert actual == expected

    with pytest.raises(sqlite3.IntegrityError, match="supported bounds"):
        conn.execute(
            """
            insert into test_readings (
              id, pool_id, tested_at, fc, source, created_at
            ) values ('bad-reading', 'example', '2026-01-01Z', 101, 'manual', '2026-01-01Z')
            """
        )
    conn.rollback()


def test_migration_dry_run_validates_current_source_snapshot(tmp_path, capsys):
    from openpool import migrate

    path = tmp_path / "source.sqlite"
    conn = db.connect(path)
    try:
        db.init_db(conn)
        db.create_pool(conn, {"id": "source", "volume_gallons": 10_000})
    finally:
        conn.close()

    assert migrate.main(["--sqlite", str(path), "--dry-run"]) == 0

    output = capsys.readouterr().out
    assert "Dry run source rows:" in output
    assert "pool_profiles: 1" in output


def test_corrupt_csi_metadata_fails_closed(conn):
    reading = db.create_reading(conn, "example", {"fc": 3, "cya": 40})
    conn.execute(
        "update test_readings set csi_meta_json = ? where id = ?",
        (sqlite3.Binary(b"\xff"), reading["id"]),
    )
    conn.commit()

    stored = db.get_reading(conn, reading["id"])

    assert stored["csi_meta"]["formula_version"] == "unknown"
    assert stored["csi_meta"]["warnings"] == ["Stored CSI provenance is invalid."]


def test_list_methods_accept_no_limit(conn):
    for hour in range(3):
        db.create_reading(
            conn,
            "example",
            {"tested_at": f"2026-06-01T0{hour}:00", "fc": hour},
        )

    assert len(db.list_readings(conn, "example", limit=2)) == 2
    assert len(db.list_readings(conn, "example", limit=None)) == 3


def test_future_schema_version_is_rejected_without_creating_tables(tmp_path):
    path = tmp_path / "future.sqlite"
    legacy = sqlite3.connect(path)
    try:
        legacy.execute(db.SCHEMA_VERSION_SQL)
        legacy.execute(
            "insert into schema_version (id, version) values (1, ?)",
            (db.CURRENT_SCHEMA_VERSION + 1,),
        )
        legacy.execute("create table future_only (value text)")
        legacy.commit()
    finally:
        legacy.close()

    conn = db.connect(path)
    try:
        with pytest.raises(RuntimeError, match="newer than supported"):
            db.init_db(conn)
        tables = {
            row["name"]
            for row in conn.execute(
                "select name from sqlite_master where type = 'table'"
            ).fetchall()
        }
    finally:
        conn.close()

    assert tables == {"schema_version", "future_only"}


def test_claimed_current_schema_must_have_current_tables(tmp_path):
    path = tmp_path / "forged-current.sqlite"
    legacy = sqlite3.connect(path)
    try:
        legacy.execute(db.SCHEMA_VERSION_SQL)
        legacy.execute(
            "insert into schema_version (id, version) values (1, ?)",
            (db.CURRENT_SCHEMA_VERSION,),
        )
        legacy.commit()
    finally:
        legacy.close()

    conn = db.connect(path)
    try:
        with pytest.raises(RuntimeError, match="claims schema version"):
            db.init_db(conn)
        tables = {
            row["name"]
            for row in conn.execute(
                "select name from sqlite_master where type = 'table'"
            ).fetchall()
        }
    finally:
        conn.close()

    assert tables == {"schema_version"}


def test_failed_migration_rolls_back_all_schema_changes(tmp_path, monkeypatch):
    path = tmp_path / "failed-migration.sqlite"

    def fail_after_ddl(conn):
        conn.execute("create table migration_artifact (value text)")
        raise RuntimeError("forced migration failure")

    monkeypatch.setattr(db, "CURRENT_SCHEMA_VERSION", 1)
    monkeypatch.setattr(db, "MIGRATIONS", ((1, fail_after_ddl),))

    conn = db.connect(path)
    try:
        with pytest.raises(RuntimeError, match="forced migration failure"):
            db.init_db(conn)
        tables = conn.execute(
            "select name from sqlite_master where type = 'table'"
        ).fetchall()
    finally:
        conn.close()

    assert tables == []


def test_unversioned_sqlite_database_upgrades_in_place(tmp_path):
    path = tmp_path / "legacy.sqlite"
    legacy = sqlite3.connect(path)
    try:
        for statement in db.SCHEMA:
            legacy.execute(statement)
        legacy.execute(
            """
            insert into pool_profiles (
              id, name, volume_gallons, created_at, updated_at
            ) values ('legacy', 'Legacy', 10000, '2026-01-01Z', '2026-01-01Z')
            """
        )
        legacy.execute(
            """
            insert into test_readings (
              id, pool_id, tested_at, fc, cc, tc, ph, ta, ch, source, created_at
            ) values (
              'reading', 'legacy', '2026-01-01Z', 3, 0.5, 99, 7.6, 80, 300,
              'manual', '2026-01-01Z'
            )
            """
        )
        legacy.commit()
    finally:
        legacy.close()

    conn = db.connect(path)
    try:
        db.init_db(conn)
        version = conn.execute("select version from schema_version").fetchone()["version"]
        reading = db.get_reading(conn, "reading")
    finally:
        conn.close()

    assert version == db.CURRENT_SCHEMA_VERSION
    assert reading["tc"] == 3.5
    assert reading["csi_meta"]["formula_version"] == db.CSI_FORMULA_VERSION


def test_upgrade_refuses_to_destroy_out_of_bounds_legacy_data(tmp_path):
    path = tmp_path / "legacy-oob.sqlite"
    legacy = sqlite3.connect(path)
    try:
        for statement in db.SCHEMA:
            legacy.execute(statement)
        legacy.execute(
            """
            insert into pool_profiles (
              id, name, volume_gallons, created_at, updated_at
            ) values ('legacy', 'Legacy', 10000, '2026-01-01Z', '2026-01-01Z')
            """
        )
        legacy.execute(
            """
            insert into test_readings (
              id, pool_id, tested_at, fc, source, created_at
            ) values ('reading', 'legacy', '2026-01-01Z', 101, 'manual', '2026-01-01Z')
            """
        )
        legacy.commit()
    finally:
        legacy.close()

    conn = db.connect(path)
    try:
        with pytest.raises(RuntimeError, match="test_readings=1"):
            db.init_db(conn)
        preserved = conn.execute(
            "select fc from test_readings where id = 'reading'"
        ).fetchone()["fc"]
    finally:
        conn.close()

    assert preserved == 101


def test_upgrade_removes_unimplemented_metric_preference(tmp_path):
    path = tmp_path / "legacy-metric.sqlite"
    legacy = sqlite3.connect(path)
    try:
        for statement in db.SCHEMA:
            legacy.execute(statement)
        legacy.execute(
            """
            insert into pool_profiles (
              id, name, volume_gallons, unit_system, created_at, updated_at
            ) values ('legacy', 'Legacy', 10000, 'metric', '2026-01-01Z', '2026-01-01Z')
            """
        )
        legacy.commit()
    finally:
        legacy.close()

    conn = db.connect(path)
    try:
        db.init_db(conn)
        pool = db.get_pool(conn, "legacy")
        with pytest.raises(sqlite3.IntegrityError, match="metric display"):
            conn.execute("update pool_profiles set unit_system = 'metric' where id = 'legacy'")
        conn.rollback()
    finally:
        conn.close()

    assert pool["unit_system"] == "us"


def test_default_pool_uses_configured_timezone(conn):
    pool = db.get_pool(conn, "example")
    assert pool["timezone"] == "America/Phoenix"


def test_settings_default_pool_id_falls_back_to_pool(monkeypatch):
    from openpool.config import get_settings

    monkeypatch.delenv("OPENPOOL_DEFAULT_POOL_ID", raising=False)

    assert get_settings().default_pool_id == "pool"


def test_ensure_default_pool_creates_pool_by_default(tmp_path):
    conn = db.connect(tmp_path / "openpool.sqlite")
    try:
        db.init_db(conn)

        pool = db.ensure_default_pool(conn, timezone_name="America/Phoenix")

        assert pool["id"] == "pool"
        assert pool["timezone"] == "America/Phoenix"
    finally:
        conn.close()


def test_create_pool_without_id_uses_pool(tmp_path):
    conn = db.connect(tmp_path / "openpool.sqlite")
    try:
        db.init_db(conn)

        pool = db.create_pool(conn, {})

        assert pool["id"] == "pool"
    finally:
        conn.close()


def test_ensure_default_pool_adopts_sole_existing_pool(tmp_path, caplog):
    conn = db.connect(tmp_path / "openpool.sqlite")
    try:
        db.init_db(conn)
        db.create_pool(conn, {"id": "example", "timezone": "America/Phoenix"})
        caplog.set_level(logging.WARNING, logger="openpool.db")

        pool = db.ensure_default_pool(conn, "pool", "UTC")

        assert pool["id"] == "example"
        assert [existing["id"] for existing in db.list_pools(conn)] == ["example"]
        assert "using existing pool id 'example'" in caplog.text
    finally:
        conn.close()


def test_startup_adopts_sole_existing_pool_for_pages(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    db_path = tmp_path / "openpool.sqlite"
    conn = db.connect(db_path)
    try:
        db.init_db(conn)
        db.create_pool(conn, {"id": "example", "timezone": "America/Phoenix"})
    finally:
        conn.close()

    monkeypatch.delenv("OPENPOOL_DATABASE_URL", raising=False)
    monkeypatch.delenv("OPENPOOL_DEFAULT_POOL_ID", raising=False)
    monkeypatch.setenv("OPENPOOL_DB", str(db_path))
    monkeypatch.setenv("OPENPOOL_TIMEZONE", "America/Phoenix")

    from openpool.main import create_app

    with TestClient(create_app()) as test_client:
        dashboard = test_client.get("/")
        help_page = test_client.get("/help")
        pools = test_client.get("/api/pools").json()

    assert dashboard.status_code == 200
    assert help_page.status_code == 200
    assert "http://testserver/api/pools/example/readings" in help_page.text
    assert [pool["id"] for pool in pools] == ["example"]


def test_connect_rejects_libpq_keyword_dsn():
    with pytest.raises(ValueError, match="libpq keyword/value DSNs are not supported"):
        db.connect("host=localhost dbname=openpool")


def test_database_url_rejects_malformed_value(monkeypatch):
    from openpool.config import get_settings

    monkeypatch.setenv("OPENPOOL_DATABASE_URL", "not-a-postgres-url")

    with pytest.raises(ValueError, match="OPENPOOL_DATABASE_URL must be a postgresql:// URL"):
        get_settings()


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


def test_humanize_number_formats_for_display():
    # Whole numbers drop the trailing ".0"; large values group by thousands.
    assert services.humanize_number(80.0) == "80"
    assert services.humanize_number(3000) == "3,000"
    assert services.humanize_number(7.2) == "7.2"
    assert services.humanize_number(1.50) == "1.5"
    # None becomes empty so the same filter is safe in form inputs.
    assert services.humanize_number(None) == ""
    # Form fields opt out of grouping so the value re-parses as a number.
    assert services.humanize_number(3000, grouping=False) == "3000"


def test_status_summary_levels(conn):
    pool = db.get_pool(conn, "example")
    assert services.status_summary(pool, None)["level"] == "empty"

    now = datetime(2026, 6, 1, 18, 0, tzinfo=UTC)

    db.create_reading(
        conn,
        "example",
        {"tested_at": "2026-06-01T10:00", "fc": 0.5, "cya": 40},
    )
    low = db.latest_reading(conn, "example")
    assert services.status_summary(pool, low, now=now)["level"] == "danger"

    db.create_reading(
        conn,
        "example",
        {"tested_at": "2026-06-01T10:30", "fc": 6, "cya": 40},
    )
    good = db.latest_reading(conn, "example")
    assert services.status_summary(pool, good, now=now)["level"] == "good"
    assert services.status_summary(pool, good, now=now)["text"] == "All readings in range"


def test_recommendation_requires_fresh_same_day_reading(conn):
    pool = db.get_pool(conn, "example")
    reading = {"tested_at": "2026-06-01T12:00:00Z", "fc": 1, "cya": 40}

    fresh = services.recommended_actions(
        pool, reading, now=datetime(2026, 6, 1, 18, 0, tzinfo=UTC)
    )
    stale = services.recommended_actions(
        pool, reading, now=datetime(2026, 6, 2, 1, 0, tzinfo=UTC)
    )

    assert fresh[0]["kind"] == "chlorine"
    assert stale[0]["kind"] == "retest"
    assert "more than 12 hours old" in stale[0]["why"]
    assert "dose" not in stale[0]


def test_gate_p_freshness_seconds_inside_and_outside(reference_examples, conn):
    case = reference_examples["gate_p_critical"]["freshness"]
    pool = db.get_pool(conn, "example")
    tested_at = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    reading = {"tested_at": tested_at.isoformat().replace("+00:00", "Z"), "fc": 1, "cya": 40}

    inside = services.recommended_actions(
        pool, reading, now=tested_at + timedelta(seconds=case["inside_seconds"])
    )
    outside = services.recommended_actions(
        pool, reading, now=tested_at + timedelta(seconds=case["outside_seconds"])
    )

    assert case["max_age_hours"] == 12
    assert timedelta(hours=case["max_age_hours"]) == services.FRESH_READING_MAX_AGE
    assert inside[0]["kind"] == "chlorine"
    assert outside[0]["kind"] == "retest"
    assert "more than 12 hours old" in outside[0]["why"]


def test_recommendation_requires_current_pool_local_day(conn):
    pool = db.get_pool(conn, "example")
    reading = {"tested_at": "2026-06-02T06:00:00Z", "fc": 1, "cya": 40}

    actions = services.recommended_actions(
        pool,
        reading,
        now=datetime(2026, 6, 2, 8, 0, tzinfo=UTC),
    )

    assert actions[0]["kind"] == "retest"
    assert "not from today" in actions[0]["why"]
    assert "dose" not in actions[0]


def test_chlorine_addition_after_reading_suppresses_recommendation(conn):
    pool = db.get_pool(conn, "example")
    reading = {"tested_at": "2026-06-01T12:00:00Z", "fc": 1, "cya": 40}
    additions = [
        {
            "chemical": "liquid_chlorine",
            "added_at": "2026-06-01T13:00:00Z",
        }
    ]

    actions = services.recommended_actions(
        pool,
        reading,
        additions,
        now=datetime(2026, 6, 1, 18, 0, tzinfo=UTC),
    )

    assert actions[0]["kind"] == "retest"
    assert "Chlorine was logged" in actions[0]["why"]
    assert "dose" not in actions[0]


def test_chlorine_addition_at_reading_time_suppresses_recommendation(conn):
    pool = db.get_pool(conn, "example")
    reading = {"tested_at": "2026-06-01T12:00:00Z", "fc": 1, "cya": 40}
    additions = [
        {"chemical": "cal_hypo", "added_at": "2026-06-01T12:00:00Z"}
    ]

    actions = services.recommended_actions(
        pool,
        reading,
        additions,
        now=datetime(2026, 6, 1, 18, 0, tzinfo=UTC),
    )

    assert actions[0]["kind"] == "retest"
    assert "dose" not in actions[0]


def test_chlorine_addition_with_bad_timestamp_fails_closed(conn):
    pool = db.get_pool(conn, "example")
    reading = {"tested_at": "2026-06-01T12:00:00Z", "fc": 1, "cya": 40}
    additions = [{"chemical": "dichlor", "added_at": "not-a-time"}]

    actions = services.recommended_actions(
        pool,
        reading,
        additions,
        now=datetime(2026, 6, 1, 18, 0, tzinfo=UTC),
    )

    assert actions[0]["kind"] == "retest"
    assert "no valid timestamp" in actions[0]["why"]
    assert "dose" not in actions[0]


def test_non_chlorine_addition_does_not_suppress_recommendation(conn):
    pool = db.get_pool(conn, "example")
    reading = {"tested_at": "2026-06-01T12:00:00Z", "fc": 1, "cya": 40}
    additions = [{"chemical": "salt", "added_at": "2026-06-01T13:00:00Z"}]

    actions = services.recommended_actions(
        pool,
        reading,
        additions,
        now=datetime(2026, 6, 1, 18, 0, tzinfo=UTC),
    )

    assert actions[0]["kind"] == "chlorine"


def test_above_chart_cya_returns_retest_action_without_dose(conn):
    pool = db.get_pool(conn, "example")
    reading = {"tested_at": "2026-06-01T12:00:00Z", "fc": 1, "cya": 200}

    actions = services.recommended_actions(
        pool, reading, now=datetime(2026, 6, 1, 18, 0, tzinfo=UTC)
    )

    assert actions[0]["kind"] == "retest"
    assert "above the supported" in actions[0]["why"]
    assert "dose" not in actions[0]


def test_status_summary_cautions_for_non_chlorine_out_of_range(conn):
    pool = db.get_pool(conn, "example")
    reading = {
        "tested_at": "2026-06-01T12:00:00Z",
        "fc": 6,
        "cya": 40,
        "ch": 900,
        "csi": 0.7,
    }

    status = services.status_summary(
        pool, reading, now=datetime(2026, 6, 1, 18, 0, tzinfo=UTC)
    )

    assert status["level"] == "caution"
    assert status["text"] == "2 readings outside range"
    assert "Balanced" not in status["text"]
    assert "chlorine" not in status["text"].lower()


def test_status_summary_uses_singular_outside_range_copy(conn):
    pool = db.get_pool(conn, "example")
    reading = {
        "tested_at": "2026-06-01T12:00:00Z",
        "fc": 6,
        "cya": 40,
        "ch": 900,
    }

    status = services.status_summary(
        pool, reading, now=datetime(2026, 6, 1, 18, 0, tzinfo=UTC)
    )

    assert status["level"] == "caution"
    assert status["text"] == "1 reading outside range"
