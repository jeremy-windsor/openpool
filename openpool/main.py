from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from openpool import __version__, db
from openpool.config import get_settings
from openpool.routers import api, export, pages
from openpool.security import reject_cross_origin_writes

PACKAGE_DIR = Path(__file__).parent


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    conn = db.connect(settings.db_path)
    try:
        db.init_db(conn)
        db.ensure_default_pool(conn, settings.default_pool_id)
    finally:
        conn.close()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="openpool",
        version=__version__,
        description="Local-first pool chemistry logbook and calculator.",
        lifespan=lifespan,
    )
    app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
    app.middleware("http")(reject_cross_origin_writes)
    app.include_router(api.router)
    app.include_router(export.router)
    app.include_router(pages.router)
    return app


app = create_app()


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run("openpool.main:app", host=settings.host, port=settings.port, reload=False)
