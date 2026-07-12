from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

import pytest

from openpool import db, migrate


@pytest.fixture(scope="session")
def postgres_url() -> str:
    url = os.getenv("OPENPOOL_TEST_DATABASE_URL")
    if not url:
        pytest.skip("OPENPOOL_TEST_DATABASE_URL is not set")
    return url


@pytest.fixture
def postgres_conn(postgres_url: str):
    try:
        conn = db.connect(postgres_url)
        db.init_db(conn)
    except Exception as exc:
        pytest.skip(f"PostgreSQL test database unavailable: {exc}")
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def pg_pool_id(postgres_conn) -> str:
    pool_id = f"pgtest_{uuid.uuid4().hex}"
    try:
        yield pool_id
    finally:
        postgres_conn.execute("delete from pool_profiles where id = ?", (pool_id,))
        postgres_conn.commit()


def _create_records(conn: db.Connection, pool_id: str) -> None:
    db.create_pool(
        conn,
        {
            "id": pool_id,
            "name": "Postgres Test Pool",
            "volume_gallons": 18_500,
            "spa_volume_gallons": 450,
            "surface": "plaster",
            "sanitizer": "liquid_chlorine",
            "unit_system": "us",
            "timezone": "America/Phoenix",
            "default_chlorine_percent": 12.5,
            "default_cya_target": 50,
            "default_salt_target": 3200,
            "jug_size_fl_oz": 128,
            "bag_size_lbs": 40,
            "share_enabled": 1,
            "share_token": "postgres-test-token",
            "include_notes_in_share": 1,
            "notes": "private",
        },
    )
    reading = db.create_reading(
        conn,
        pool_id,
        {
            "tested_at": "2026-06-07T09:15",
            "fc": 4,
            "cc": 0.5,
            "ph": 7.6,
            "ta": 70,
            "ch": 350,
            "cya": 40,
            "salt": 3000,
            "water_temp_f": 84,
            "notes": "reading notes",
        },
    )
    db.create_addition(
        conn,
        pool_id,
        {
            "added_at": "2026-06-07T10:35",
            "chemical": "liquid_chlorine",
            "strength_percent": 12.5,
            "amount": 64,
            "unit": "fl_oz",
            "reason": "maintenance",
            "linked_reading_id": reading["id"],
            "notes": "addition notes",
        },
    )
    db.create_maintenance(
        conn,
        pool_id,
        {
            "event_at": "2026-06-08T08:00",
            "event_type": "backwash",
            "notes": "maintenance notes",
        },
    )


def _drop_dynamic(row: dict[str, Any], extra: set[str] | None = None) -> dict[str, Any]:
    ignored = {"id", "created_at", "updated_at"} | (extra or set())
    return {key: value for key, value in row.items() if key not in ignored}


def _snapshot(conn: db.Connection, pool_id: str) -> dict[str, Any]:
    pool = db.get_pool(conn, pool_id)
    latest = db.latest_reading(conn, pool_id)
    assert pool is not None
    assert latest is not None
    return {
        "pool": _drop_dynamic(pool),
        "latest": _drop_dynamic(latest),
        "readings": [_drop_dynamic(row) for row in db.list_readings(conn, pool_id)],
        "additions": [
            _drop_dynamic(row, {"linked_reading_id"})
            for row in db.list_additions(conn, pool_id)
        ],
        "maintenance": [_drop_dynamic(row) for row in db.list_maintenance(conn, pool_id)],
    }


def test_postgres_crud_matches_sqlite(tmp_path: Path, postgres_conn, pg_pool_id: str):
    sqlite_conn = db.connect(tmp_path / "openpool.sqlite")
    try:
        db.init_db(sqlite_conn)
        _create_records(sqlite_conn, pg_pool_id)
        _create_records(postgres_conn, pg_pool_id)

        assert _snapshot(postgres_conn, pg_pool_id) == _snapshot(sqlite_conn, pg_pool_id)
    finally:
        sqlite_conn.close()


def test_migration_copies_sqlite_rows_to_postgres(
    tmp_path: Path,
    postgres_url: str,
    postgres_conn,
    pg_pool_id: str,
):
    sqlite_path = tmp_path / "source.sqlite"
    sqlite_conn = db.connect(sqlite_path)
    try:
        db.init_db(sqlite_conn)
        _create_records(sqlite_conn, pg_pool_id)
    finally:
        sqlite_conn.close()

    assert migrate.main(["--sqlite", str(sqlite_path), "--postgres", postgres_url]) == 0

    pool = db.get_pool(postgres_conn, pg_pool_id)
    assert pool["name"] == "Postgres Test Pool"
    assert len(db.list_readings(postgres_conn, pg_pool_id)) == 1
    assert len(db.list_additions(postgres_conn, pg_pool_id)) == 1
    assert len(db.list_maintenance(postgres_conn, pg_pool_id)) == 1
