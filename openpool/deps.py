from __future__ import annotations

from collections.abc import Iterator

from openpool import db
from openpool.config import get_settings


def get_db() -> Iterator[db.Connection]:
    settings = get_settings()
    conn = db.connect(settings.connection_target)
    try:
        yield conn
    finally:
        conn.close()
