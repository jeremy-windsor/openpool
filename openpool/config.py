from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

POSTGRES_SCHEMES = ("postgresql://", "postgres://")


@dataclass(frozen=True)
class Settings:
    app_name: str
    db_path: Path
    database_url: str | None
    host: str
    port: int
    default_pool_id: str
    default_timezone: str
    build_sha: str
    build_ref: str

    @property
    def backend(self) -> Literal["sqlite", "postgresql"]:
        return "postgresql" if self.database_url else "sqlite"

    @property
    def connection_target(self) -> str | Path:
        return self.database_url or self.db_path


def get_settings() -> Settings:
    database_url = os.getenv("OPENPOOL_DATABASE_URL") or None
    if database_url:
        if "://" in database_url and not database_url.startswith(POSTGRES_SCHEMES):
            raise ValueError("OPENPOOL_DATABASE_URL must use postgresql:// or postgres://")
        if "://" not in database_url:
            raise ValueError(
                "OPENPOOL_DATABASE_URL must be a postgresql:// URL; "
                "libpq keyword/value DSNs are not supported"
            )

    return Settings(
        app_name=os.getenv("OPENPOOL_APP_NAME", "openpool"),
        db_path=Path(os.getenv("OPENPOOL_DB", "data/openpool.sqlite")),
        database_url=database_url,
        host=os.getenv("OPENPOOL_HOST", "127.0.0.1"),
        port=int(os.getenv("OPENPOOL_PORT", "5280")),
        default_pool_id=os.getenv("OPENPOOL_DEFAULT_POOL_ID", "example"),
        default_timezone=os.getenv("OPENPOOL_TIMEZONE") or os.getenv("TZ", "UTC"),
        build_sha=os.getenv("OPENPOOL_BUILD_SHA", "unknown"),
        build_ref=os.getenv("OPENPOOL_BUILD_REF", "unknown"),
    )
