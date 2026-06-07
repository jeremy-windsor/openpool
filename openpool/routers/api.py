from __future__ import annotations

from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException

from openpool import __version__, db, services
from openpool.config import get_settings
from openpool.deps import get_db
from openpool.schemas import AdditionIn, CalculationIn, PoolIn, PoolUpdate, ReadingIn, dump_model

router = APIRouter()


def _not_found(pool_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"pool not found: {pool_id}")


@router.get("/api/health")
def health(conn: Connection = Depends(get_db)) -> dict[str, object]:
    settings = get_settings()
    conn.execute("select 1")
    return {
        "ok": True,
        "app": "openpool",
        "version": __version__,
        "buildSha": settings.build_sha,
        "buildRef": settings.build_ref,
    }


@router.get("/api/version")
def version() -> dict[str, object]:
    settings = get_settings()
    return {
        "app": "openpool",
        "version": __version__,
        "buildSha": settings.build_sha,
        "buildRef": settings.build_ref,
    }


@router.get("/api/pools")
def list_pools(conn: Connection = Depends(get_db)) -> list[dict[str, object]]:
    return db.public_pools(db.list_pools(conn))


@router.post("/api/pools", status_code=201)
def create_pool(pool: PoolIn, conn: Connection = Depends(get_db)) -> dict[str, object]:
    try:
        created = db.create_pool(conn, dump_model(pool, exclude_none=True))
        return db.public_pool(created)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/pools/{pool_id}")
def get_pool(pool_id: str, conn: Connection = Depends(get_db)) -> dict[str, object]:
    try:
        pool = db.get_pool(conn, pool_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not pool:
        raise _not_found(pool_id)
    return db.public_pool(pool)


@router.put("/api/pools/{pool_id}")
def update_pool(
    pool_id: str,
    pool: PoolUpdate,
    conn: Connection = Depends(get_db),
) -> dict[str, object]:
    try:
        updated = db.update_pool(
            conn,
            pool_id,
            dump_model(pool, exclude_none=True, exclude_unset=True),
        )
        return db.public_pool(updated)
    except KeyError as exc:
        raise _not_found(pool_id) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/pools/{pool_id}/readings")
def list_readings(pool_id: str, conn: Connection = Depends(get_db)) -> list[dict[str, object]]:
    try:
        if not db.get_pool(conn, pool_id):
            raise _not_found(pool_id)
        return db.list_readings(conn, pool_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/pools/{pool_id}/readings", status_code=201)
def create_reading(
    pool_id: str,
    reading: ReadingIn,
    conn: Connection = Depends(get_db),
) -> dict[str, object]:
    try:
        return db.create_reading(conn, pool_id, dump_model(reading, exclude_none=True))
    except KeyError as exc:
        raise _not_found(pool_id) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/pools/{pool_id}/readings/latest")
def latest_reading(pool_id: str, conn: Connection = Depends(get_db)) -> dict[str, object] | None:
    try:
        if not db.get_pool(conn, pool_id):
            raise _not_found(pool_id)
        return db.latest_reading(conn, pool_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/pools/{pool_id}/additions")
def list_additions(pool_id: str, conn: Connection = Depends(get_db)) -> list[dict[str, object]]:
    try:
        if not db.get_pool(conn, pool_id):
            raise _not_found(pool_id)
        return db.list_additions(conn, pool_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/pools/{pool_id}/additions", status_code=201)
def create_addition(
    pool_id: str,
    addition: AdditionIn,
    conn: Connection = Depends(get_db),
) -> dict[str, object]:
    try:
        return db.create_addition(conn, pool_id, dump_model(addition, exclude_none=True))
    except KeyError as exc:
        raise _not_found(pool_id) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/pools/{pool_id}/calculate")
def calculate(
    pool_id: str,
    calculation: CalculationIn,
    conn: Connection = Depends(get_db),
) -> dict[str, object]:
    try:
        pool = db.get_pool(conn, pool_id)
        if not pool:
            raise _not_found(pool_id)
        return services.calculate_goal(pool, calculation.goal, dump_model(calculation))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/pools/{pool_id}/share.json")
@router.get("/share/{pool_id}.json")
def share_json(
    pool_id: str,
    token: str | None = None,
    conn: Connection = Depends(get_db),
) -> dict[str, object]:
    try:
        pool = db.get_pool(conn, pool_id)
        if not pool:
            raise _not_found(pool_id)
        if not services.share_access_allowed(pool, token):
            raise HTTPException(
                status_code=403,
                detail="share endpoint is disabled or token is invalid",
            )
        return services.build_snapshot(conn, pool_id)
    except KeyError as exc:
        raise _not_found(pool_id) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
