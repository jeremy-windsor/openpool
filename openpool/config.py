from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str
    db_path: Path
    host: str
    port: int
    default_pool_id: str


def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("OPENPOOL_APP_NAME", "openpool"),
        db_path=Path(os.getenv("OPENPOOL_DB", "data/openpool.sqlite")),
        host=os.getenv("OPENPOOL_HOST", "127.0.0.1"),
        port=int(os.getenv("OPENPOOL_PORT", "5280")),
        default_pool_id=os.getenv("OPENPOOL_DEFAULT_POOL_ID", "example"),
    )

