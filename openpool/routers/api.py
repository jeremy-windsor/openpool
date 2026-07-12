from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from openpool import __version__, db, services
from openpool.config import get_settings
from openpool.deps import get_db
from openpool.schemas import (
    AdditionIn,
    AdditionUpdate,
    CalculationIn,
    MaintenanceIn,
    MaintenanceUpdate,
    PoolIn,
    PoolUpdate,
    ReadingIn,
    dump_model,
)

router = APIRouter()


def _not_found(pool_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"pool not found: {pool_id}")


@router.get("/api/health")
def health(conn: db.Connection = Depends(get_db)) -> dict[str, object]:
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
def list_pools(conn: db.Connection = Depends(get_db)) -> list[dict[str, object]]:
    return db.public_pools(db.list_pools(conn))


@router.post("/api/pools", status_code=201)
def create_pool(pool: PoolIn, conn: db.Connection = Depends(get_db)) -> dict[str, object]:
    try:
        created = db.create_pool(conn, dump_model(pool, exclude_none=True))
        return db.public_pool(created)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/pools/{pool_id}")
def get_pool(pool_id: str, conn: db.Connection = Depends(get_db)) -> dict[str, object]:
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
    conn: db.Connection = Depends(get_db),
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
def list_readings(pool_id: str, conn: db.Connection = Depends(get_db)) -> list[dict[str, object]]:
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
    conn: db.Connection = Depends(get_db),
) -> dict[str, object]:
    try:
        return db.create_reading(conn, pool_id, dump_model(reading, exclude_none=True))
    except KeyError as exc:
        raise _not_found(pool_id) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/pools/{pool_id}/readings/latest")
def latest_reading(
    pool_id: str,
    conn: db.Connection = Depends(get_db),
) -> dict[str, object] | None:
    try:
        if not db.get_pool(conn, pool_id):
            raise _not_found(pool_id)
        return db.latest_reading(conn, pool_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/pools/{pool_id}/readings/{reading_id}")
def get_reading(
    pool_id: str,
    reading_id: str,
    conn: db.Connection = Depends(get_db),
) -> dict[str, object]:
    try:
        if not db.get_pool(conn, pool_id):
            raise _not_found(pool_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    reading = db.get_reading(conn, reading_id)
    if not reading or reading["pool_id"] != pool_id:
        raise HTTPException(status_code=404, detail=f"reading not found: {reading_id}")
    return reading


@router.put("/api/pools/{pool_id}/readings/{reading_id}")
def update_reading(
    pool_id: str,
    reading_id: str,
    reading: ReadingIn,
    conn: db.Connection = Depends(get_db),
) -> dict[str, object]:
    try:
        return db.update_reading(
            conn,
            pool_id,
            reading_id,
            dump_model(reading, exclude_unset=True),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"not found: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api/pools/{pool_id}/readings/{reading_id}", status_code=204)
def delete_reading(
    pool_id: str,
    reading_id: str,
    conn: db.Connection = Depends(get_db),
) -> None:
    try:
        db.delete_reading(conn, pool_id, reading_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"not found: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/pools/{pool_id}/additions")
def list_additions(pool_id: str, conn: db.Connection = Depends(get_db)) -> list[dict[str, object]]:
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
    conn: db.Connection = Depends(get_db),
) -> dict[str, object]:
    try:
        return db.create_addition(conn, pool_id, dump_model(addition, exclude_none=True))
    except KeyError as exc:
        raise _not_found(pool_id) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/pools/{pool_id}/additions/{addition_id}")
def update_addition(
    pool_id: str,
    addition_id: str,
    addition: AdditionUpdate,
    conn: db.Connection = Depends(get_db),
) -> dict[str, object]:
    try:
        return db.update_addition(
            conn,
            pool_id,
            addition_id,
            dump_model(addition, exclude_unset=True),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"not found: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api/pools/{pool_id}/additions/{addition_id}", status_code=204)
def delete_addition(
    pool_id: str,
    addition_id: str,
    conn: db.Connection = Depends(get_db),
) -> None:
    try:
        db.delete_addition(conn, pool_id, addition_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"not found: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/pools/{pool_id}/maintenance")
def list_maintenance(
    pool_id: str,
    conn: db.Connection = Depends(get_db),
) -> list[dict[str, object]]:
    try:
        if not db.get_pool(conn, pool_id):
            raise _not_found(pool_id)
        return db.list_maintenance(conn, pool_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/pools/{pool_id}/maintenance", status_code=201)
def create_maintenance(
    pool_id: str,
    event: MaintenanceIn,
    conn: db.Connection = Depends(get_db),
) -> dict[str, object]:
    try:
        return db.create_maintenance(conn, pool_id, dump_model(event, exclude_none=True))
    except KeyError as exc:
        raise _not_found(pool_id) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/pools/{pool_id}/maintenance/{event_id}")
def update_maintenance(
    pool_id: str,
    event_id: str,
    event: MaintenanceUpdate,
    conn: db.Connection = Depends(get_db),
) -> dict[str, object]:
    try:
        return db.update_maintenance(
            conn,
            pool_id,
            event_id,
            dump_model(event, exclude_unset=True),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"not found: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api/pools/{pool_id}/maintenance/{event_id}", status_code=204)
def delete_maintenance(
    pool_id: str,
    event_id: str,
    conn: db.Connection = Depends(get_db),
) -> None:
    try:
        db.delete_maintenance(conn, pool_id, event_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"not found: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/pools/{pool_id}/calculate")
def calculate(
    pool_id: str,
    calculation: CalculationIn,
    conn: db.Connection = Depends(get_db),
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
    conn: db.Connection = Depends(get_db),
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
