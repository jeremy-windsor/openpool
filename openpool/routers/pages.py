from __future__ import annotations

from sqlite3 import Connection
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from openpool import db, services
from openpool.config import get_settings
from openpool.deps import get_db
from openpool.schemas import (
    AdditionIn,
    PoolIn,
    ReadingIn,
    dump_model,
    model_field_names,
    validate_model,
)

templates = Jinja2Templates(directory=str(Path(__file__).parents[1] / "templates"))
router = APIRouter()


async def _form_data(request: Request) -> dict[str, str]:
    body = (await request.body()).decode()
    parsed = parse_qs(body, keep_blank_values=True)
    return {key: values[-1] for key, values in parsed.items()}


def _empty_to_none(data: dict[str, str]) -> dict[str, str | None]:
    return {key: (None if value == "" else value) for key, value in data.items()}


def _pool_id() -> str:
    return get_settings().default_pool_id


@router.get("/")
def dashboard(request: Request, conn: Connection = Depends(get_db)):
    pool_id = _pool_id()
    snapshot = services.build_snapshot(conn, pool_id)
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "title": "Dashboard",
            "snapshot": snapshot,
        },
    )


@router.get("/readings/new")
def new_reading(request: Request, conn: Connection = Depends(get_db)):
    pool_id = _pool_id()
    latest = db.latest_reading(conn, pool_id)
    return templates.TemplateResponse(
        "reading_form.html",
        {"request": request, "title": "New reading", "pool_id": pool_id, "latest": latest},
    )


@router.post("/readings/new")
async def save_reading(request: Request, conn: Connection = Depends(get_db)):
    pool_id = _pool_id()
    form = _empty_to_none(await _form_data(request))
    try:
        reading = validate_model(ReadingIn, form)
        db.create_reading(conn, pool_id, dump_model(reading, exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse("/", status_code=303)


@router.get("/additions/new")
def new_addition(request: Request):
    return templates.TemplateResponse(
        "addition_form.html",
        {"request": request, "title": "New addition"},
    )


@router.post("/additions/new")
async def save_addition(request: Request, conn: Connection = Depends(get_db)):
    pool_id = _pool_id()
    form = _empty_to_none(await _form_data(request))
    try:
        addition = validate_model(AdditionIn, form)
        db.create_addition(conn, pool_id, dump_model(addition, exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse("/history", status_code=303)


@router.get("/history")
def history(request: Request, conn: Connection = Depends(get_db)):
    pool_id = _pool_id()
    pool = db.get_pool(conn, pool_id)
    timezone_name = pool.get("timezone") if pool else "UTC"
    readings = db.list_readings(conn, pool_id)
    for row in readings:
        row["tested_at_local"] = db.local_timestamp(row.get("tested_at"), timezone_name)
    return templates.TemplateResponse(
        "history.html",
        {
            "request": request,
            "title": "History",
            "pool_id": pool_id,
            "readings": readings,
            "additions": db.list_additions(conn, pool_id),
        },
    )


@router.get("/calculator")
def calculator(
    request: Request,
    goal: str = "raise_fc",
    current: float | None = None,
    target: float | None = None,
    pool_gallons: float | None = None,
    strength: float | None = None,
    conn: Connection = Depends(get_db),
):
    pool_id = _pool_id()
    pool = db.get_pool(conn, pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail=f"pool not found: {pool_id}")

    result = None
    if current is not None and target is not None:
        try:
            result = services.calculate_goal(
                pool,
                goal,
                {
                    "current": current,
                    "target": target,
                    "pool_gallons": pool_gallons,
                    "strength": strength,
                },
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return templates.TemplateResponse(
        "calculator.html",
        {
            "request": request,
            "title": "Calculator",
            "pool": pool,
            "goal": goal,
            "current": current,
            "target": target,
            "pool_gallons": pool_gallons,
            "strength": strength,
            "result": result,
        },
    )


@router.get("/settings")
def settings_page(request: Request, conn: Connection = Depends(get_db)):
    pool_id = _pool_id()
    pool = db.get_pool(conn, pool_id)
    return templates.TemplateResponse(
        "settings.html",
        {"request": request, "title": "Settings", "pool": pool},
    )


@router.post("/settings")
async def save_settings(request: Request, conn: Connection = Depends(get_db)):
    pool_id = _pool_id()
    form = _empty_to_none(await _form_data(request))
    try:
        pool = db.get_pool(conn, pool_id)
        if not pool:
            raise KeyError(pool_id)
        current = {key: pool.get(key) for key in model_field_names(PoolIn)}
        settings = validate_model(PoolIn, {**current, **form})
        db.update_pool(conn, pool_id, dump_model(settings, exclude_none=True))
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse("/settings", status_code=303)


@router.get("/share/{pool_id}")
def share_page(
    pool_id: str,
    request: Request,
    token: str | None = None,
    conn: Connection = Depends(get_db),
):
    try:
        pool = db.get_pool(conn, pool_id)
        if not pool:
            raise HTTPException(status_code=404, detail=f"pool not found: {pool_id}")
        if not services.share_access_allowed(pool, token):
            raise HTTPException(
                status_code=403,
                detail="share endpoint is disabled or token is invalid",
            )
        snapshot = services.build_snapshot(conn, pool_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"pool not found: {pool_id}") from exc
    return templates.TemplateResponse(
        "share.html",
        {"request": request, "title": "Share", "snapshot": snapshot},
    )
