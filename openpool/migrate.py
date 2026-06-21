from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from openpool import db

TABLES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "pool_profiles",
        (
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
            "created_at",
            "updated_at",
        ),
    ),
    (
        "test_readings",
        (
            "id",
            "pool_id",
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
            "created_at",
        ),
    ),
    (
        "chemical_additions",
        (
            "id",
            "pool_id",
            "added_at",
            "chemical",
            "strength_percent",
            "amount",
            "unit",
            "reason",
            "linked_reading_id",
            "notes",
            "created_at",
        ),
    ),
    (
        "maintenance_events",
        (
            "id",
            "pool_id",
            "event_at",
            "event_type",
            "notes",
            "created_at",
        ),
    ),
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Copy OpenPool data from SQLite to PostgreSQL.",
    )
    parser.add_argument(
        "--sqlite",
        default=os.getenv("OPENPOOL_DB", "data/openpool.sqlite"),
        help="Source SQLite database path. Defaults to OPENPOOL_DB or data/openpool.sqlite.",
    )
    parser.add_argument(
        "--postgres",
        default=os.getenv("OPENPOOL_DATABASE_URL"),
        help="Destination PostgreSQL URL. Defaults to OPENPOOL_DATABASE_URL.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print source row counts without writing to PostgreSQL.",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Clear destination tables in the same transaction before copying.",
    )
    return parser


def _count_rows(conn: db.Connection, table: str) -> int:
    row = conn.execute(f"select count(*) as count from {table}").fetchone()
    return int(db.row_to_dict(row)["count"])


def _table_counts(conn: db.Connection) -> dict[str, int]:
    return {table: _count_rows(conn, table) for table, _columns in TABLES}


def _fetch_rows(conn: db.Connection, table: str, columns: tuple[str, ...]) -> list[dict[str, Any]]:
    column_sql = ", ".join(columns)
    return db.rows_to_dicts(conn.execute(f"select {column_sql} from {table}").fetchall())


def _truncate_destination(conn: db.Connection) -> None:
    table_sql = ", ".join(table for table, _columns in TABLES)
    conn.execute(f"truncate table {table_sql}")


def _copy_table(
    src: db.Connection,
    dst: db.Connection,
    table: str,
    columns: tuple[str, ...],
) -> tuple[int, int]:
    rows = _fetch_rows(src, table, columns)
    if not rows:
        return 0, 0

    column_sql = ", ".join(columns)
    placeholders = ", ".join("?" for _column in columns)
    insert_sql = (
        f"insert into {table} ({column_sql}) values ({placeholders}) "
        "on conflict do nothing"
    )

    inserted = 0
    for row in rows:
        cursor = dst.execute(insert_sql, tuple(row[column] for column in columns))
        inserted += max(cursor.rowcount, 0)
    return len(rows), inserted


def _copy_all(src: db.Connection, dst: db.Connection) -> dict[str, tuple[int, int]]:
    return {
        table: _copy_table(src, dst, table, columns)
        for table, columns in TABLES
    }


def _print_counts(prefix: str, counts: dict[str, int]) -> None:
    print(prefix)
    for table, count in counts.items():
        print(f"  {table}: {count}")


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)

    sqlite_path = Path(args.sqlite)
    if not sqlite_path.exists():
        parser.error(f"SQLite database does not exist: {sqlite_path}")

    if not args.dry_run:
        if not args.postgres:
            parser.error("--postgres or OPENPOOL_DATABASE_URL is required")
        if not db.is_postgres_url(args.postgres):
            parser.error("PostgreSQL destination must use postgresql:// or postgres://")

    src = db.connect(sqlite_path)
    try:
        source_counts = _table_counts(src)
        if args.dry_run:
            _print_counts("Dry run source rows:", source_counts)
            return 0

        dst = db.connect(args.postgres, autocommit=False)
        try:
            db.init_db(dst)
            try:
                if args.truncate:
                    _truncate_destination(dst)
                results = _copy_all(src, dst)
                dst.commit()
            except Exception:
                dst.rollback()
                raise
        finally:
            dst.close()
    finally:
        src.close()

    print("Migration complete:")
    for table, (seen, inserted) in results.items():
        print(f"  {table}: {inserted} inserted, {seen - inserted} skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
