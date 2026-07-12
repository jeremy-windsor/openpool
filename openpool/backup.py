from __future__ import annotations

import argparse
import os
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path


def backup_sqlite(source: Path, destination: Path) -> Path:
    source = source.resolve()
    destination = destination.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"SQLite database does not exist: {source}")
    if source == destination:
        raise ValueError("backup destination must differ from the live database")
    if destination.exists():
        raise FileExistsError(f"backup destination already exists: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)

        source_conn = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
        destination_conn = sqlite3.connect(temporary_path)
        try:
            source_conn.execute("pragma busy_timeout = 5000")
            destination_conn.execute("pragma busy_timeout = 5000")
            source_conn.backup(destination_conn)
            integrity = destination_conn.execute("pragma integrity_check").fetchone()[0]
            if integrity != "ok":
                raise RuntimeError(f"backup integrity check failed: {integrity}")
        finally:
            destination_conn.close()
            source_conn.close()

        os.replace(temporary_path, destination)
        temporary_path = None
        return destination
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a verified OpenPool SQLite backup.")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(os.getenv("OPENPOOL_DB", "data/openpool.sqlite")),
        help="Live SQLite database path. Defaults to OPENPOOL_DB.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Backup filename. Defaults to SOURCE.parent/backups/openpool-TIMESTAMP.sqlite.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or args.source.parent / "backups" / f"openpool-{timestamp}.sqlite"
    try:
        written = backup_sqlite(args.source, output)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print(f"Backup complete: {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
