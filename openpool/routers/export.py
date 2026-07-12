from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse

from openpool import db
from openpool.deps import get_db

router = APIRouter()


def _safe_csv_value(value: object) -> object:
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _safe_csv_row(row: dict[str, object]) -> dict[str, object]:
    return {key: _safe_csv_value(value) for key, value in row.items()}


@router.get("/api/pools/{pool_id}/export/readings.csv")
def export_readings(pool_id: str, conn: db.Connection = Depends(get_db)) -> Response:
    try:
        if not db.get_pool(conn, pool_id):
            raise HTTPException(status_code=404, detail=f"pool not found: {pool_id}")
        rows = db.list_readings(conn, pool_id, limit=10_000)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    fieldnames = [
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
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(_safe_csv_row(row) for row in rows)
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{pool_id}-readings.csv"'},
    )


@router.get("/api/pools/{pool_id}/export/additions.csv")
def export_additions(pool_id: str, conn: db.Connection = Depends(get_db)) -> Response:
    try:
        if not db.get_pool(conn, pool_id):
            raise HTTPException(status_code=404, detail=f"pool not found: {pool_id}")
        rows = db.list_additions(conn, pool_id, limit=10_000)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    fieldnames = [
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
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(_safe_csv_row(row) for row in rows)
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{pool_id}-additions.csv"'},
    )


@router.get("/api/pools/{pool_id}/export/maintenance.csv")
def export_maintenance(pool_id: str, conn: db.Connection = Depends(get_db)) -> Response:
    try:
        if not db.get_pool(conn, pool_id):
            raise HTTPException(status_code=404, detail=f"pool not found: {pool_id}")
        rows = db.list_maintenance(conn, pool_id, limit=10_000)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    fieldnames = [
        "id",
        "pool_id",
        "event_at",
        "event_type",
        "notes",
        "created_at",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(_safe_csv_row(row) for row in rows)
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{pool_id}-maintenance.csv"'},
    )


@router.get("/api/pools/{pool_id}/export/all.json")
def export_all(pool_id: str, conn: db.Connection = Depends(get_db)) -> JSONResponse:
    try:
        pool = db.get_pool(conn, pool_id)
        if not pool:
            raise HTTPException(status_code=404, detail=f"pool not found: {pool_id}")
        payload = {
            "pool": db.public_pool(pool),
            "readings": db.list_readings(conn, pool_id, limit=10_000),
            "additions": db.list_additions(conn, pool_id, limit=10_000),
            "maintenance": db.list_maintenance(conn, pool_id, limit=10_000),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse(payload)
