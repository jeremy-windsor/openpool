from __future__ import annotations

from collections.abc import Iterator
from sqlite3 import Connection

from openpool import db
from openpool.config import get_settings


def get_db() -> Iterator[Connection]:
    settings = get_settings()
    conn = db.connect(settings.db_path)
    try:
        yield conn
    finally:
        conn.close()
