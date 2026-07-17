from __future__ import annotations

import json
import logging
import re
import secrets
import sqlite3
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from openpool.chemistry.csi import DEFAULT_TDS_PPM, DEFAULT_WATER_TEMP_F, calculate_csi

DEFAULT_POOL_ID = "pool"
POOL_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MIN_SHARE_TOKEN_LENGTH = 16
POSTGRES_SCHEMES = ("postgresql://", "postgres://")
REAL_TYPE_RE = re.compile(r"\breal\b", re.IGNORECASE)
LOGGER = logging.getLogger(__name__)
CSI_FORMULA_VERSION = "openpool-csi-v1"
CURRENT_SCHEMA_VERSION = 4


class PoolAlreadyExistsError(ValueError):
    """Raised when a pool identifier is already present."""


class Cursor(Protocol):
    rowcount: int

    def fetchone(self) -> Any | None:
        ...

    def fetchall(self) -> list[Any]:
        ...


class Connection(Protocol):
    def execute(self, statement: str, parameters: Iterable[Any] = ()) -> Cursor:
        ...

    def commit(self) -> None:
        ...

    def rollback(self) -> None:
        ...

    def close(self) -> None:
        ...


class _PgConnection:
    backend = "postgresql"

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def execute(self, statement: str, parameters: Iterable[Any] = ()) -> Any:
        sql = statement.replace("?", "%s")
        return self._conn.execute(sql, tuple(parameters))

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()


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

SCHEMA_VERSION_SQL = """
create table if not exists schema_version (
  id integer primary key check (id = 1),
  version integer not null
)
"""

TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "pool_profiles": (
        "id", "name", "volume_gallons", "spa_volume_gallons", "surface",
        "sanitizer", "unit_system", "timezone", "default_chlorine_percent",
        "default_cya_target", "default_salt_target", "jug_size_fl_oz",
        "bag_size_lbs", "share_enabled", "share_token", "include_notes_in_share",
        "notes", "created_at", "updated_at",
    ),
    "test_readings": (
        "id", "pool_id", "tested_at", "fc", "cc", "tc", "ph", "ta", "ch",
        "cya", "salt", "borates", "water_temp_f", "filter_pressure", "csi",
        "source", "notes", "created_at", "csi_meta_json",
    ),
    "chemical_additions": (
        "id", "pool_id", "added_at", "chemical", "strength_percent", "amount",
        "unit", "reason", "linked_reading_id", "notes", "created_at",
    ),
    "maintenance_events": (
        "id", "pool_id", "event_at", "event_type", "notes", "created_at",
    ),
}

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
    "ph",
    "ta",
    "ch",
    "cya",
    "salt",
    "borates",
    "water_temp_f",
    "filter_pressure",
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

NUMERIC_BOUNDS: dict[str, tuple[float | None, float | None]] = {
    "volume_gallons": (0, 1_000_000),
    "spa_volume_gallons": (0, 1_000_000),
    "default_chlorine_percent": (1, 100),
    "default_cya_target": (0, 500),
    "default_salt_target": (0, 50_000),
    "fc": (0, 100),
    "cc": (0, 100),
    "ph": (0, 14),
    "ta": (0, 2_000),
    "ch": (0, 2_000),
    "cya": (0, 500),
    "salt": (0, 50_000),
    "borates": (0, 200),
    "water_temp_f": (32, 120),
    "filter_pressure": (0, 100),
    "strength_percent": (1, 100),
    "amount": (0, 100_000),
}


def is_postgres_url(target: str | Path) -> bool:
    return isinstance(target, str) and target.startswith(POSTGRES_SCHEMES)


def _connect_postgres(database_url: str, *, autocommit: bool = True) -> Connection:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError(
            "PostgreSQL support requires installing openpool with the postgres extra"
        ) from exc
    return _PgConnection(psycopg.connect(database_url, autocommit=autocommit, row_factory=dict_row))


def _connect_sqlite(db_path: str | Path) -> Connection:
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


def connect(target: str | Path, *, autocommit: bool = True) -> Connection:
    if is_postgres_url(target):
        return _connect_postgres(str(target), autocommit=autocommit)
    if isinstance(target, str) and "://" in target:
        raise ValueError("unsupported database URL scheme; use postgresql:// or postgres://")
    if isinstance(target, str) and "=" in target:
        raise ValueError(
            "libpq keyword/value DSNs are not supported; use a postgresql:// URL"
        )
    return _connect_sqlite(target)


def _schema_statement(conn: Connection, statement: str) -> str:
    if getattr(conn, "backend", "sqlite") == "postgresql":
        return REAL_TYPE_RE.sub("double precision", statement)
    return statement


def _existing_schema_version(conn: Connection) -> int | None:
    if getattr(conn, "backend", "sqlite") == "postgresql":
        row = conn.execute("select to_regclass('schema_version') as table_name").fetchone()
        if row_to_dict(row)["table_name"] is None:
            return None
    else:
        row = conn.execute(
            "select 1 as present from sqlite_master "
            "where type = 'table' and name = 'schema_version'"
        ).fetchone()
        if row is None:
            return None

    version_row = conn.execute(
        "select version from schema_version where id = 1"
    ).fetchone()
    if version_row is None:
        return None
    return int(row_to_dict(version_row)["version"])


def _validate_current_schema(conn: Connection) -> None:
    for table, columns in TABLE_COLUMNS.items():
        column_sql = ", ".join(columns)
        try:
            conn.execute(f"select {column_sql} from {table} where 1 = 0")
        except Exception as exc:
            raise RuntimeError(
                f"database claims schema version {CURRENT_SCHEMA_VERSION}, but "
                f"{table} does not match that schema"
            ) from exc


def require_current_schema(conn: Connection) -> None:
    version = _existing_schema_version(conn)
    if version != CURRENT_SCHEMA_VERSION:
        found = "unversioned" if version is None else str(version)
        raise RuntimeError(
            f"database schema is {found}; expected version {CURRENT_SCHEMA_VERSION}. "
            "Start OpenPool once to upgrade it before migrating data."
        )
    _validate_current_schema(conn)


def init_db(conn: Connection) -> None:
    try:
        conn.execute("begin")
        version = _existing_schema_version(conn)
        if version is not None and version > CURRENT_SCHEMA_VERSION:
            raise RuntimeError(
                f"database schema version {version} is newer than supported version "
                f"{CURRENT_SCHEMA_VERSION}"
            )
        if version == CURRENT_SCHEMA_VERSION:
            _validate_current_schema(conn)

        for statement in SCHEMA:
            conn.execute(_schema_statement(conn, statement))
        conn.execute(SCHEMA_VERSION_SQL)
        if version is None:
            conn.execute("insert into schema_version (id, version) values (1, 0)")
            version = 0
        for migration_version, migration in MIGRATIONS:
            if migration_version <= version:
                continue
            migration(conn)
            conn.execute(
                "update schema_version set version = ? where id = 1",
                (migration_version,),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


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


def row_to_dict(row: Any | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def rows_to_dicts(rows: Iterable[Any]) -> list[dict[str, Any]]:
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


def _share_enabled(value: Any) -> bool:
    if isinstance(value, str):
        return value in {"1", "true", "on"}
    return value is True or value == 1


def _validate_share_token(data: dict[str, Any], existing: dict[str, Any] | None = None) -> None:
    enabled = data.get("share_enabled", existing.get("share_enabled") if existing else None)
    token = data.get("share_token")
    existing_token = existing.get("share_token") if existing else None
    if token and len(str(token)) < MIN_SHARE_TOKEN_LENGTH:
        raise ValueError("share token must be at least 16 characters")
    if _share_enabled(enabled) and not token:
        if existing_token:
            if len(str(existing_token)) < MIN_SHARE_TOKEN_LENGTH:
                raise ValueError("share token must be at least 16 characters")
            data.pop("share_token", None)
            return
        data["share_token"] = generate_share_token()


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
            lower, upper = NUMERIC_BOUNDS.get(key, (None, None))
            if lower is not None and value < lower:
                raise ValueError(f"{key} must be at least {lower:g}")
            if upper is not None and value > upper:
                raise ValueError(f"{key} must be at most {upper:g}")
            if key in {"volume_gallons", "spa_volume_gallons", "amount"} and value <= 0:
                raise ValueError(f"{key} must be greater than 0")
        if key in {"share_enabled", "include_notes_in_share"} and value is not None:
            value = 1 if value in {True, "true", "1", "on"} else 0
        cleaned[key] = value
    return cleaned


def _is_unique_violation(exc: Exception) -> bool:
    if isinstance(exc, sqlite3.IntegrityError):
        return getattr(exc, "sqlite_errorcode", None) in {
            sqlite3.SQLITE_CONSTRAINT_PRIMARYKEY,
            sqlite3.SQLITE_CONSTRAINT_UNIQUE,
        }
    return getattr(exc, "sqlstate", None) == "23505"


def ensure_default_pool(
    conn: Connection,
    pool_id: str = DEFAULT_POOL_ID,
    timezone_name: str = "UTC",
) -> dict[str, Any]:
    existing = get_pool(conn, pool_id)
    if existing:
        return existing

    pools = list_pools(conn)
    if len(pools) == 1:
        adopted = pools[0]
        LOGGER.warning(
            "Configured default pool id %r is missing; using existing pool id %r "
            "instead of creating a second default pool.",
            pool_id,
            adopted["id"],
        )
        return adopted

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


def create_pool(conn: Connection, payload: dict[str, Any]) -> dict[str, Any]:
    data = _clean_payload(payload, POOL_FIELDS)
    _validate_share_token(data)
    validate_timezone_name(data.get("timezone") or "UTC")
    pool_id = validate_pool_id(str(data.get("id") or DEFAULT_POOL_ID))
    if get_pool(conn, pool_id):
        raise PoolAlreadyExistsError(f"pool already exists: {pool_id}")
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
        "default_cya_target": (
            40.0 if data.get("default_cya_target") is None else data["default_cya_target"]
        ),
        "default_salt_target": (
            3200.0 if data.get("default_salt_target") is None else data["default_salt_target"]
        ),
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
    try:
        conn.execute(
            f"insert into pool_profiles ({columns}) values ({placeholders})",
            tuple(row.values()),
        )
    except Exception as exc:
        if _is_unique_violation(exc):
            raise PoolAlreadyExistsError(f"pool already exists: {pool_id}") from exc
        raise
    conn.commit()
    return get_pool(conn, pool_id) or row


def update_pool(conn: Connection, pool_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    validate_pool_id(pool_id)
    existing = get_pool(conn, pool_id)
    if not existing:
        raise KeyError(pool_id)
    data = _clean_payload(payload, POOL_FIELDS - {"id"})
    _validate_share_token(data, existing)
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


def list_pools(conn: Connection) -> list[dict[str, Any]]:
    return rows_to_dicts(conn.execute("select * from pool_profiles order by name").fetchall())


def get_pool(conn: Connection, pool_id: str) -> dict[str, Any] | None:
    validate_pool_id(pool_id)
    row = conn.execute("select * from pool_profiles where id = ?", (pool_id,)).fetchone()
    return row_to_dict(row)


def _computed_csi(reading: dict[str, Any]) -> tuple[float | None, str]:
    """Compute CSI and persist enough provenance to explain the result."""
    result = calculate_csi(
        ph=reading.get("ph"),
        ta=reading.get("ta"),
        ch=reading.get("ch"),
        cya=reading.get("cya"),
        water_temp_f=reading.get("water_temp_f"),
        salt=reading.get("salt"),
        borates=reading.get("borates"),
    )
    inputs = {
        key: reading.get(key)
        for key in ("ph", "ta", "ch", "cya", "water_temp_f", "salt", "borates")
    }
    defaults = {}
    if reading.get("water_temp_f") is None:
        defaults["water_temp_f"] = DEFAULT_WATER_TEMP_F
    if reading.get("salt") is None:
        defaults["tds_ppm"] = DEFAULT_TDS_PPM
    metadata = {
        "formula_version": CSI_FORMULA_VERSION,
        "inputs": inputs,
        "defaults": defaults,
        "warnings": result.warnings,
    }
    return result.value, json.dumps(metadata, separators=(",", ":"), sort_keys=True)


def _reading_dict(row: Any | None) -> dict[str, Any] | None:
    reading = row_to_dict(row)
    if reading is None:
        return None
    raw_metadata = reading.get("csi_meta_json")
    if raw_metadata:
        try:
            metadata = json.loads(raw_metadata)
            if not isinstance(metadata, dict) or not isinstance(metadata.get("warnings"), list):
                raise ValueError("CSI provenance must be an object with a warnings list")
            reading["csi_meta"] = metadata
        except (TypeError, ValueError, UnicodeDecodeError):
            reading["csi_meta"] = {
                "formula_version": "unknown",
                "warnings": ["Stored CSI provenance is invalid."],
            }
    else:
        reading["csi_meta"] = None
    return reading


def _migrate_csi_metadata(conn: Connection) -> None:
    conn.execute("alter table test_readings add column csi_meta_json text")
    rows = conn.execute("select * from test_readings").fetchall()
    for raw_row in rows:
        reading = dict(raw_row)
        csi, metadata = _computed_csi(reading)
        conn.execute(
            "update test_readings set tc = ?, csi = ?, csi_meta_json = ? where id = ?",
            (
                reading.get("fc") + reading.get("cc")
                if reading.get("fc") is not None and reading.get("cc") is not None
                else None,
                csi,
                metadata,
                reading["id"],
            ),
        )


def _migrate_linked_reading_integrity(conn: Connection) -> None:
    conn.execute(
        """
        update chemical_additions
        set linked_reading_id = null
        where linked_reading_id is not null
          and not exists (
            select 1 from test_readings
            where test_readings.id = chemical_additions.linked_reading_id
              and test_readings.pool_id = chemical_additions.pool_id
          )
        """
    )
    conn.execute(
        "create unique index if not exists idx_test_readings_id_pool "
        "on test_readings(id, pool_id)"
    )
    if getattr(conn, "backend", "sqlite") == "postgresql":
        conn.execute(
            """
            alter table chemical_additions
            add constraint fk_chemical_additions_reading_pool
            foreign key (linked_reading_id, pool_id)
            references test_readings(id, pool_id)
            """
        )
        return

    conn.execute(
        """
        create table chemical_additions_new (
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
          created_at text not null,
          foreign key (linked_reading_id, pool_id)
            references test_readings(id, pool_id)
        )
        """
    )
    conn.execute(
        """
        insert into chemical_additions_new (
          id, pool_id, added_at, chemical, strength_percent, amount, unit,
          reason, linked_reading_id, notes, created_at
        )
        select id, pool_id, added_at, chemical, strength_percent, amount, unit,
               reason, linked_reading_id, notes, created_at
        from chemical_additions
        """
    )
    conn.execute("drop table chemical_additions")
    conn.execute("alter table chemical_additions_new rename to chemical_additions")
    conn.execute(
        "create index idx_chemical_additions_pool_time "
        "on chemical_additions(pool_id, added_at desc)"
    )


def _migrate_numeric_constraints(conn: Connection) -> None:
    preflight_checks = (
        (
            "pool_profiles",
            "not (volume_gallons > 0 and volume_gallons <= 1000000 "
            "and (spa_volume_gallons is null or "
            "(spa_volume_gallons > 0 and spa_volume_gallons <= 1000000)) "
            "and default_chlorine_percent between 1 and 100 "
            "and default_cya_target between 0 and 500 "
            "and default_salt_target between 0 and 50000)",
        ),
        (
            "test_readings",
            "not ((fc is null or fc between 0 and 100) "
            "and (cc is null or cc between 0 and 100) "
            "and (ph is null or ph between 0 and 14) "
            "and (ta is null or ta between 0 and 2000) "
            "and (ch is null or ch between 0 and 2000) "
            "and (cya is null or cya between 0 and 500) "
            "and (salt is null or salt between 0 and 50000) "
            "and (borates is null or borates between 0 and 200) "
            "and (water_temp_f is null or water_temp_f between 32 and 120) "
            "and (filter_pressure is null or filter_pressure between 0 and 100))",
        ),
        (
            "chemical_additions",
            "not (amount > 0 and amount <= 100000 "
            "and (strength_percent is null or strength_percent between 1 and 100))",
        ),
    )
    violations = []
    for table, condition in preflight_checks:
        row = conn.execute(
            f"select count(*) as count from {table} where {condition}"
        ).fetchone()
        count = int(row_to_dict(row)["count"])
        if count:
            violations.append(f"{table}={count}")
    if violations:
        raise RuntimeError(
            "database has values outside supported numeric bounds; repair them before "
            f"upgrading: {', '.join(violations)}"
        )

    if getattr(conn, "backend", "sqlite") == "postgresql":
        constraints = (
            (
                "pool_profiles",
                "ck_pool_profiles_numeric_bounds",
                "volume_gallons <= 1000000 and "
                "(spa_volume_gallons is null or spa_volume_gallons between 0 and 1000000) and "
                "default_chlorine_percent between 1 and 100 and "
                "default_cya_target between 0 and 500 and "
                "default_salt_target between 0 and 50000",
            ),
            (
                "test_readings",
                "ck_test_readings_numeric_bounds",
                "(fc is null or fc between 0 and 100) and "
                "(cc is null or cc between 0 and 100) and "
                "(ph is null or ph between 0 and 14) and "
                "(ta is null or ta between 0 and 2000) and "
                "(ch is null or ch between 0 and 2000) and "
                "(cya is null or cya between 0 and 500) and "
                "(salt is null or salt between 0 and 50000) and "
                "(borates is null or borates between 0 and 200) and "
                "(water_temp_f is null or water_temp_f between 32 and 120) and "
                "(filter_pressure is null or filter_pressure between 0 and 100)",
            ),
            (
                "chemical_additions",
                "ck_chemical_additions_numeric_bounds",
                "amount > 0 and amount <= 100000 and "
                "(strength_percent is null or strength_percent between 1 and 100)",
            ),
        )
        for table, name, expression in constraints:
            conn.execute(f"alter table {table} add constraint {name} check ({expression})")
        return

    triggers = (
        (
            "pool_profiles",
            "not (new.volume_gallons > 0 and new.volume_gallons <= 1000000 "
            "and (new.spa_volume_gallons is null or "
            "(new.spa_volume_gallons > 0 and new.spa_volume_gallons <= 1000000)) "
            "and new.default_chlorine_percent between 1 and 100 "
            "and new.default_cya_target between 0 and 500 "
            "and new.default_salt_target between 0 and 50000)",
        ),
        (
            "test_readings",
            "not ((new.fc is null or new.fc between 0 and 100) "
            "and (new.cc is null or new.cc between 0 and 100) "
            "and (new.ph is null or new.ph between 0 and 14) "
            "and (new.ta is null or new.ta between 0 and 2000) "
            "and (new.ch is null or new.ch between 0 and 2000) "
            "and (new.cya is null or new.cya between 0 and 500) "
            "and (new.salt is null or new.salt between 0 and 50000) "
            "and (new.borates is null or new.borates between 0 and 200) "
            "and (new.water_temp_f is null or new.water_temp_f between 32 and 120) "
            "and (new.filter_pressure is null or new.filter_pressure between 0 and 100))",
        ),
        (
            "chemical_additions",
            "not (new.amount > 0 and new.amount <= 100000 "
            "and (new.strength_percent is null or new.strength_percent between 1 and 100))",
        ),
    )
    for table, condition in triggers:
        for operation in ("insert", "update"):
            conn.execute(
                f"""
                create trigger ck_{table}_numeric_bounds_{operation}
                before {operation} on {table}
                when {condition}
                begin
                  select raise(abort, 'numeric value outside supported bounds');
                end
                """
            )


def _migrate_metric_mode(conn: Connection) -> None:
    conn.execute("update pool_profiles set unit_system = 'us' where unit_system <> 'us'")
    if getattr(conn, "backend", "sqlite") == "postgresql":
        conn.execute(
            "alter table pool_profiles add constraint ck_pool_profiles_unit_system_us "
            "check (unit_system = 'us')"
        )
        return
    for operation in ("insert", "update"):
        conn.execute(
            f"""
            create trigger ck_pool_profiles_unit_system_us_{operation}
            before {operation} on pool_profiles
            when new.unit_system <> 'us'
            begin
              select raise(abort, 'metric display is not implemented; unit_system must be us');
            end
            """
        )


MIGRATIONS = (
    (1, _migrate_csi_metadata),
    (2, _migrate_linked_reading_integrity),
    (3, _migrate_numeric_constraints),
    (4, _migrate_metric_mode),
)


def create_reading(
    conn: Connection,
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
    data["tc"] = fc + cc if fc is not None and cc is not None else None
    data["csi"], data["csi_meta_json"] = _computed_csi(data)
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
        "csi_meta_json": data.get("csi_meta_json"),
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


def get_reading(conn: Connection, reading_id: str) -> dict[str, Any] | None:
    row = conn.execute("select * from test_readings where id = ?", (reading_id,)).fetchone()
    return _reading_dict(row)


def update_reading(
    conn: Connection,
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
    fc, cc = merged.get("fc"), merged.get("cc")
    data["tc"] = fc + cc if fc is not None and cc is not None else None
    data["csi"], data["csi_meta_json"] = _computed_csi(merged)
    if not data:
        return existing

    assignments = ", ".join(f"{key} = ?" for key in data)
    conn.execute(
        f"update test_readings set {assignments} where id = ?",
        (*data.values(), reading_id),
    )
    conn.commit()
    return get_reading(conn, reading_id) or merged


def delete_reading(conn: Connection, pool_id: str, reading_id: str) -> None:
    validate_pool_id(pool_id)
    existing = get_reading(conn, reading_id)
    if not existing or existing["pool_id"] != pool_id:
        raise KeyError(reading_id)
    conn.execute("delete from test_readings where id = ?", (reading_id,))
    conn.commit()


def list_readings(
    conn: Connection,
    pool_id: str,
    limit: int | None = 100,
    start_utc: str | None = None,
    end_utc: str | None = None,
) -> list[dict[str, Any]]:
    validate_pool_id(pool_id)
    query = """
        select * from test_readings
        where pool_id = ?
    """
    params: list[Any] = [pool_id]
    if start_utc:
        query += " and tested_at >= ?"
        params.append(start_utc)
    if end_utc:
        query += " and tested_at < ?"
        params.append(end_utc)
    query += " order by tested_at desc, created_at desc"
    if limit is not None:
        query += " limit ?"
        params.append(limit)
    return [_reading_dict(row) or {} for row in conn.execute(query, tuple(params)).fetchall()]


def latest_reading(conn: Connection, pool_id: str) -> dict[str, Any] | None:
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
    return _reading_dict(row)


def _validate_linked_reading(
    conn: Connection, pool_id: str, linked_reading_id: str | None
) -> None:
    if linked_reading_id is None:
        return
    reading = get_reading(conn, linked_reading_id)
    if not reading:
        raise ValueError(f"linked reading not found: {linked_reading_id}")
    if reading["pool_id"] != pool_id:
        raise ValueError("linked reading must belong to the same pool")


def create_addition(
    conn: Connection,
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
    _validate_linked_reading(conn, pool_id, data.get("linked_reading_id"))

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


def get_addition(conn: Connection, addition_id: str) -> dict[str, Any] | None:
    row = conn.execute("select * from chemical_additions where id = ?", (addition_id,)).fetchone()
    return row_to_dict(row)


def update_addition(
    conn: Connection,
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
    _validate_linked_reading(conn, pool_id, merged.get("linked_reading_id"))
    if not data:
        return existing

    assignments = ", ".join(f"{key} = ?" for key in data)
    conn.execute(
        f"update chemical_additions set {assignments} where id = ?",
        (*data.values(), addition_id),
    )
    conn.commit()
    return get_addition(conn, addition_id) or merged


def delete_addition(conn: Connection, pool_id: str, addition_id: str) -> None:
    validate_pool_id(pool_id)
    existing = get_addition(conn, addition_id)
    if not existing or existing["pool_id"] != pool_id:
        raise KeyError(addition_id)
    conn.execute("delete from chemical_additions where id = ?", (addition_id,))
    conn.commit()


def list_additions(
    conn: Connection,
    pool_id: str,
    limit: int | None = 100,
    start_utc: str | None = None,
    end_utc: str | None = None,
) -> list[dict[str, Any]]:
    validate_pool_id(pool_id)
    query = """
        select * from chemical_additions
        where pool_id = ?
    """
    params: list[Any] = [pool_id]
    if start_utc:
        query += " and added_at >= ?"
        params.append(start_utc)
    if end_utc:
        query += " and added_at < ?"
        params.append(end_utc)
    query += " order by added_at desc, created_at desc"
    if limit is not None:
        query += " limit ?"
        params.append(limit)
    return rows_to_dicts(
        conn.execute(query, tuple(params)).fetchall()
    )


def create_maintenance(
    conn: Connection,
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


def get_maintenance(conn: Connection, event_id: str) -> dict[str, Any] | None:
    row = conn.execute("select * from maintenance_events where id = ?", (event_id,)).fetchone()
    return row_to_dict(row)


def list_maintenance(
    conn: Connection,
    pool_id: str,
    limit: int | None = 100,
    start_utc: str | None = None,
    end_utc: str | None = None,
) -> list[dict[str, Any]]:
    validate_pool_id(pool_id)
    query = """
        select * from maintenance_events
        where pool_id = ?
    """
    params: list[Any] = [pool_id]
    if start_utc:
        query += " and event_at >= ?"
        params.append(start_utc)
    if end_utc:
        query += " and event_at < ?"
        params.append(end_utc)
    query += " order by event_at desc, created_at desc"
    if limit is not None:
        query += " limit ?"
        params.append(limit)
    return rows_to_dicts(
        conn.execute(query, tuple(params)).fetchall()
    )


def update_maintenance(
    conn: Connection,
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


def delete_maintenance(conn: Connection, pool_id: str, event_id: str) -> None:
    validate_pool_id(pool_id)
    existing = get_maintenance(conn, event_id)
    if not existing or existing["pool_id"] != pool_id:
        raise KeyError(event_id)
    conn.execute("delete from maintenance_events where id = ?", (event_id,))
    conn.commit()
