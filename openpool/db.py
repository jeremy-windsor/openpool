from __future__ import annotations

import re
import secrets
import sqlite3
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from openpool.chemistry.csi import calculate_csi

POOL_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MIN_SHARE_TOKEN_LENGTH = 16


SCHEMA = (
    """
    create table if not exists pool_profiles (
      id text primary key,
      name text not null,
      volume_gallons real not null check (volume_gallons > 0),
      spa_volume_gallons real,
      surface text not null default 'plaster',
      sanitizer text not null default 'liquid_chlorine',
      unit_system text not null default 'us',
      timezone text not null default 'UTC',
      default_chlorine_percent real not null default 10.0,
      default_cya_target real not null default 40.0,
      default_salt_target real not null default 3200.0,
      jug_size_fl_oz real not null default 128.0,
      bag_size_lbs real not null default 40.0,
      share_enabled integer not null default 0,
      share_token text,
      include_notes_in_share integer not null default 0,
      notes text,
      created_at text not null,
      updated_at text not null
    )
    """,
    """
    create table if not exists test_readings (
      id text primary key,
      pool_id text not null references pool_profiles(id) on delete cascade,
      tested_at text not null,
      fc real,
      cc real,
      tc real,
      ph real,
      ta real,
      ch real,
      cya real,
      salt real,
      borates real,
      water_temp_f real,
      filter_pressure real,
      csi real,
      source text not null default 'manual',
      notes text,
      created_at text not null
    )
    """,
    """
    create table if not exists chemical_additions (
      id text primary key,
      pool_id text not null references pool_profiles(id) on delete cascade,
      added_at text not null,
      chemical text not null,
      strength_percent real,
      amount real not null,
      unit text not null,
      reason text,
      linked_reading_id text references test_readings(id) on delete set null,
      notes text,
      created_at text not null
    )
    """,
    """
    create table if not exists maintenance_events (
      id text primary key,
      pool_id text not null references pool_profiles(id) on delete cascade,
      event_at text not null,
      event_type text not null,
      notes text,
      created_at text not null
    )
    """,
    """
    create index if not exists idx_test_readings_pool_time
    on test_readings(pool_id, tested_at desc)
    """,
    """
    create index if not exists idx_chemical_additions_pool_time
    on chemical_additions(pool_id, added_at desc)
    """,
    """
    create index if not exists idx_maintenance_events_pool_time
    on maintenance_events(pool_id, event_at desc)
    """,
)

POOL_FIELDS = {
    "id",
    "name",
    "volume_gallons",
    "spa_volume_gallons",
    "surface",
    "sanitizer",
    "unit_system",
    "timezone",
    "default_chlorine_percent",
    "default_cya_target",
    "default_salt_target",
    "jug_size_fl_oz",
    "bag_size_lbs",
    "share_enabled",
    "share_token",
    "include_notes_in_share",
    "notes",
}

READING_FIELDS = {
    "tested_at",
    "fc",
    "cc",
    "tc",
    "ph",
    "ta",
    "ch",
    "cya",
    "salt",
    "borates",
    "water_temp_f",
    "filter_pressure",
    "csi",
    "source",
    "notes",
}

ADDITION_FIELDS = {
    "added_at",
    "chemical",
    "strength_percent",
    "amount",
    "unit",
    "reason",
    "linked_reading_id",
    "notes",
}

MAINTENANCE_FIELDS = {
    "event_at",
    "event_type",
    "notes",
}

NUMERIC_FIELDS = {
    "volume_gallons",
    "spa_volume_gallons",
    "default_chlorine_percent",
    "default_cya_target",
    "default_salt_target",
    "jug_size_fl_oz",
    "bag_size_lbs",
    "fc",
    "cc",
    "tc",
    "ph",
    "ta",
    "ch",
    "cya",
    "salt",
    "borates",
    "water_temp_f",
    "filter_pressure",
    "csi",
    "strength_percent",
    "amount",
}


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: FastAPI runs sync dependency generators in a
    # threadpool, so an async route may touch the connection from the event-loop
    # thread. Each request still gets its own connection, so there is no shared
    # concurrent use.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    conn.execute("pragma journal_mode = wal")
    conn.execute("pragma busy_timeout = 5000")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    for statement in SCHEMA:
        conn.execute(statement)
    conn.commit()


def now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validate_timezone_name(timezone_name: str | None) -> str:
    name = timezone_name or "UTC"
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown timezone: {name}") from exc
    return name


def normalize_timestamp(value: str | None, timezone_name: str = "UTC") -> str:
    if not value:
        return now_utc()
    text = str(value).strip()
    if not text:
        return now_utc()
    original = text
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"invalid timestamp: {original}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(validate_timezone_name(timezone_name)))
    return parsed.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def local_timestamp(value: str | None, timezone_name: str = "UTC") -> str | None:
    if not value:
        return None
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return (
            parsed.astimezone(ZoneInfo(validate_timezone_name(timezone_name)))
            .replace(microsecond=0)
            .isoformat()
        )
    except ValueError:
        return text


def validate_pool_id(pool_id: str) -> str:
    if not POOL_ID_RE.fullmatch(pool_id):
        raise ValueError("pool_id must be 1-64 characters: letters, numbers, underscore, or dash")
    return pool_id


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def public_pool(pool: dict[str, Any]) -> dict[str, Any]:
    safe = dict(pool)
    safe.pop("share_token", None)
    safe.pop("notes", None)
    return safe


def public_pools(pools: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [public_pool(pool) for pool in pools]


def generate_share_token() -> str:
    return secrets.token_urlsafe(24)


def _validate_share_token(data: dict[str, Any]) -> None:
    enabled = data.get("share_enabled")
    token = data.get("share_token")
    if enabled in {1, "1", "true", "on"}:
        if not token:
            data["share_token"] = generate_share_token()
            return
        if len(str(token)) < MIN_SHARE_TOKEN_LENGTH:
            raise ValueError("share token must be at least 16 characters")


def _clean_payload(payload: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in payload.items():
        if key not in allowed:
            continue
        if value == "":
            value = None
        if key in NUMERIC_FIELDS and value is not None:
            value = float(value)
            if not isfinite(value):
                raise ValueError(f"{key} must be a finite number")
        if key in {"share_enabled", "include_notes_in_share"} and value is not None:
            value = 1 if value in {True, "true", "1", "on"} else 0
        cleaned[key] = value
    return cleaned


def ensure_default_pool(
    conn: sqlite3.Connection,
    pool_id: str = "example",
    timezone_name: str = "UTC",
) -> dict[str, Any]:
    existing = get_pool(conn, pool_id)
    if existing:
        return existing
    timezone_name = validate_timezone_name(timezone_name)
    return create_pool(
        conn,
        {
            "id": pool_id,
            "name": "Home Pool",
            "volume_gallons": 20_000,
            "surface": "plaster",
            "sanitizer": "liquid_chlorine",
            "unit_system": "us",
            "timezone": timezone_name,
        },
    )


def create_pool(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    data = _clean_payload(payload, POOL_FIELDS)
    _validate_share_token(data)
    validate_timezone_name(data.get("timezone") or "UTC")
    pool_id = validate_pool_id(str(data.get("id") or "example"))
    timestamp = now_utc()
    row = {
        "id": pool_id,
        "name": data.get("name") or "Home Pool",
        "volume_gallons": data.get("volume_gallons") or 20_000,
        "spa_volume_gallons": data.get("spa_volume_gallons"),
        "surface": data.get("surface") or "plaster",
        "sanitizer": data.get("sanitizer") or "liquid_chlorine",
        "unit_system": data.get("unit_system") or "us",
        "timezone": data.get("timezone") or "UTC",
        "default_chlorine_percent": data.get("default_chlorine_percent") or 10.0,
        "default_cya_target": data.get("default_cya_target") or 40.0,
        "default_salt_target": data.get("default_salt_target") or 3200.0,
        "jug_size_fl_oz": data.get("jug_size_fl_oz") or 128.0,
        "bag_size_lbs": data.get("bag_size_lbs") or 40.0,
        "share_enabled": data.get("share_enabled") or 0,
        "share_token": data.get("share_token"),
        "include_notes_in_share": data.get("include_notes_in_share") or 0,
        "notes": data.get("notes"),
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    columns = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    conn.execute(
        f"insert into pool_profiles ({columns}) values ({placeholders})",
        tuple(row.values()),
    )
    conn.commit()
    return get_pool(conn, pool_id) or row


def update_pool(conn: sqlite3.Connection, pool_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    validate_pool_id(pool_id)
    if not get_pool(conn, pool_id):
        raise KeyError(pool_id)
    data = _clean_payload(payload, POOL_FIELDS - {"id"})
    _validate_share_token(data)
    if "timezone" in data:
        validate_timezone_name(data.get("timezone") or "UTC")
    data["updated_at"] = now_utc()
    assignments = ", ".join(f"{key} = ?" for key in data)
    conn.execute(
        f"update pool_profiles set {assignments} where id = ?",
        (*data.values(), pool_id),
    )
    conn.commit()
    return get_pool(conn, pool_id) or {}


def list_pools(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return rows_to_dicts(conn.execute("select * from pool_profiles order by name").fetchall())


def get_pool(conn: sqlite3.Connection, pool_id: str) -> dict[str, Any] | None:
    validate_pool_id(pool_id)
    row = conn.execute("select * from pool_profiles where id = ?", (pool_id,)).fetchone()
    return row_to_dict(row)


def _computed_csi(reading: dict[str, Any]) -> float | None:
    """Compute the approximate CSI for a reading's stored values."""
    return calculate_csi(
        ph=reading.get("ph"),
        ta=reading.get("ta"),
        ch=reading.get("ch"),
        cya=reading.get("cya"),
        water_temp_f=reading.get("water_temp_f"),
        salt=reading.get("salt"),
        borates=reading.get("borates"),
    ).value


def create_reading(
    conn: sqlite3.Connection,
    pool_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    validate_pool_id(pool_id)
    pool = get_pool(conn, pool_id)
    if not pool:
        raise KeyError(pool_id)

    data = _clean_payload(payload, READING_FIELDS)
    fc = data.get("fc")
    cc = data.get("cc")
    if data.get("tc") is None and fc is not None and cc is not None:
        data["tc"] = fc + cc
    if data.get("csi") is None:
        data["csi"] = _computed_csi(data)
    row = {
        "id": uuid.uuid4().hex,
        "pool_id": pool_id,
        "tested_at": normalize_timestamp(data.get("tested_at"), pool.get("timezone") or "UTC"),
        "fc": data.get("fc"),
        "cc": data.get("cc"),
        "tc": data.get("tc"),
        "ph": data.get("ph"),
        "ta": data.get("ta"),
        "ch": data.get("ch"),
        "cya": data.get("cya"),
        "salt": data.get("salt"),
        "borates": data.get("borates"),
        "water_temp_f": data.get("water_temp_f"),
        "filter_pressure": data.get("filter_pressure"),
        "csi": data.get("csi"),
        "source": data.get("source") or "manual",
        "notes": data.get("notes"),
        "created_at": now_utc(),
    }
    columns = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    conn.execute(
        f"insert into test_readings ({columns}) values ({placeholders})",
        tuple(row.values()),
    )
    conn.commit()
    return get_reading(conn, row["id"]) or row


def get_reading(conn: sqlite3.Connection, reading_id: str) -> dict[str, Any] | None:
    row = conn.execute("select * from test_readings where id = ?", (reading_id,)).fetchone()
    return row_to_dict(row)


def update_reading(
    conn: sqlite3.Connection,
    pool_id: str,
    reading_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    pool = get_pool(conn, pool_id)
    if not pool:
        raise KeyError(pool_id)
    existing = get_reading(conn, reading_id)
    if not existing or existing["pool_id"] != pool_id:
        raise KeyError(reading_id)

    data = _clean_payload(payload, READING_FIELDS)
    if "tested_at" in data:
        data["tested_at"] = normalize_timestamp(
            data.get("tested_at"), pool.get("timezone") or "UTC"
        )
    merged = {**existing, **data}
    if "tc" not in data and ("fc" in data or "cc" in data):
        fc, cc = merged.get("fc"), merged.get("cc")
        data["tc"] = fc + cc if fc is not None and cc is not None else None
        merged["tc"] = data["tc"]
    if "csi" not in data:
        # Recompute the stored CSI from the merged reading on every edit.
        data["csi"] = _computed_csi(merged)
    if not data:
        return existing

    assignments = ", ".join(f"{key} = ?" for key in data)
    conn.execute(
        f"update test_readings set {assignments} where id = ?",
        (*data.values(), reading_id),
    )
    conn.commit()
    return get_reading(conn, reading_id) or merged


def delete_reading(conn: sqlite3.Connection, pool_id: str, reading_id: str) -> None:
    existing = get_reading(conn, reading_id)
    if not existing or existing["pool_id"] != pool_id:
        raise KeyError(reading_id)
    conn.execute("delete from test_readings where id = ?", (reading_id,))
    conn.commit()


def list_readings(conn: sqlite3.Connection, pool_id: str, limit: int = 100) -> list[dict[str, Any]]:
    validate_pool_id(pool_id)
    return rows_to_dicts(
        conn.execute(
            """
            select * from test_readings
            where pool_id = ?
            order by tested_at desc, created_at desc
            limit ?
            """,
            (pool_id, limit),
        ).fetchall()
    )


def latest_reading(conn: sqlite3.Connection, pool_id: str) -> dict[str, Any] | None:
    validate_pool_id(pool_id)
    row = conn.execute(
        """
        select * from test_readings
        where pool_id = ?
        order by tested_at desc, created_at desc
        limit 1
        """,
        (pool_id,),
    ).fetchone()
    return row_to_dict(row)


def create_addition(
    conn: sqlite3.Connection,
    pool_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    validate_pool_id(pool_id)
    pool = get_pool(conn, pool_id)
    if not pool:
        raise KeyError(pool_id)

    data = _clean_payload(payload, ADDITION_FIELDS)
    if not data.get("chemical"):
        raise ValueError("chemical is required")
    if data.get("amount") is None:
        raise ValueError("amount is required")
    if not data.get("unit"):
        raise ValueError("unit is required")

    row = {
        "id": uuid.uuid4().hex,
        "pool_id": pool_id,
        "added_at": normalize_timestamp(data.get("added_at"), pool.get("timezone") or "UTC"),
        "chemical": data["chemical"],
        "strength_percent": data.get("strength_percent"),
        "amount": data["amount"],
        "unit": data["unit"],
        "reason": data.get("reason"),
        "linked_reading_id": data.get("linked_reading_id"),
        "notes": data.get("notes"),
        "created_at": now_utc(),
    }
    columns = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    conn.execute(
        f"insert into chemical_additions ({columns}) values ({placeholders})",
        tuple(row.values()),
    )
    conn.commit()
    return get_addition(conn, row["id"]) or row


def get_addition(conn: sqlite3.Connection, addition_id: str) -> dict[str, Any] | None:
    row = conn.execute("select * from chemical_additions where id = ?", (addition_id,)).fetchone()
    return row_to_dict(row)


def update_addition(
    conn: sqlite3.Connection,
    pool_id: str,
    addition_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    pool = get_pool(conn, pool_id)
    if not pool:
        raise KeyError(pool_id)
    existing = get_addition(conn, addition_id)
    if not existing or existing["pool_id"] != pool_id:
        raise KeyError(addition_id)

    data = _clean_payload(payload, ADDITION_FIELDS)
    if "added_at" in data:
        data["added_at"] = normalize_timestamp(data.get("added_at"), pool.get("timezone") or "UTC")
    merged = {**existing, **data}
    if not merged.get("chemical"):
        raise ValueError("chemical is required")
    if merged.get("amount") is None:
        raise ValueError("amount is required")
    if not merged.get("unit"):
        raise ValueError("unit is required")
    if not data:
        return existing

    assignments = ", ".join(f"{key} = ?" for key in data)
    conn.execute(
        f"update chemical_additions set {assignments} where id = ?",
        (*data.values(), addition_id),
    )
    conn.commit()
    return get_addition(conn, addition_id) or merged


def delete_addition(conn: sqlite3.Connection, pool_id: str, addition_id: str) -> None:
    existing = get_addition(conn, addition_id)
    if not existing or existing["pool_id"] != pool_id:
        raise KeyError(addition_id)
    conn.execute("delete from chemical_additions where id = ?", (addition_id,))
    conn.commit()


def list_additions(
    conn: sqlite3.Connection,
    pool_id: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    validate_pool_id(pool_id)
    return rows_to_dicts(
        conn.execute(
            """
            select * from chemical_additions
            where pool_id = ?
            order by added_at desc, created_at desc
            limit ?
            """,
            (pool_id, limit),
        ).fetchall()
    )


def create_maintenance(
    conn: sqlite3.Connection,
    pool_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    validate_pool_id(pool_id)
    pool = get_pool(conn, pool_id)
    if not pool:
        raise KeyError(pool_id)

    data = _clean_payload(payload, MAINTENANCE_FIELDS)
    if not data.get("event_type"):
        raise ValueError("event_type is required")

    row = {
        "id": uuid.uuid4().hex,
        "pool_id": pool_id,
        "event_at": normalize_timestamp(data.get("event_at"), pool.get("timezone") or "UTC"),
        "event_type": data["event_type"],
        "notes": data.get("notes"),
        "created_at": now_utc(),
    }
    columns = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    conn.execute(
        f"insert into maintenance_events ({columns}) values ({placeholders})",
        tuple(row.values()),
    )
    conn.commit()
    return get_maintenance(conn, row["id"]) or row


def get_maintenance(conn: sqlite3.Connection, event_id: str) -> dict[str, Any] | None:
    row = conn.execute("select * from maintenance_events where id = ?", (event_id,)).fetchone()
    return row_to_dict(row)


def list_maintenance(
    conn: sqlite3.Connection,
    pool_id: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    validate_pool_id(pool_id)
    return rows_to_dicts(
        conn.execute(
            """
            select * from maintenance_events
            where pool_id = ?
            order by event_at desc, created_at desc
            limit ?
            """,
            (pool_id, limit),
        ).fetchall()
    )


def update_maintenance(
    conn: sqlite3.Connection,
    pool_id: str,
    event_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    pool = get_pool(conn, pool_id)
    if not pool:
        raise KeyError(pool_id)
    existing = get_maintenance(conn, event_id)
    if not existing or existing["pool_id"] != pool_id:
        raise KeyError(event_id)

    data = _clean_payload(payload, MAINTENANCE_FIELDS)
    if "event_at" in data:
        data["event_at"] = normalize_timestamp(data.get("event_at"), pool.get("timezone") or "UTC")
    if "event_type" in data and not data.get("event_type"):
        raise ValueError("event_type is required")
    if not data:
        return existing

    assignments = ", ".join(f"{key} = ?" for key in data)
    conn.execute(
        f"update maintenance_events set {assignments} where id = ?",
        (*data.values(), event_id),
    )
    conn.commit()
    return get_maintenance(conn, event_id) or {**existing, **data}


def delete_maintenance(conn: sqlite3.Connection, pool_id: str, event_id: str) -> None:
    existing = get_maintenance(conn, event_id)
    if not existing or existing["pool_id"] != pool_id:
        raise KeyError(event_id)
    conn.execute("delete from maintenance_events where id = ?", (event_id,))
    conn.commit()
