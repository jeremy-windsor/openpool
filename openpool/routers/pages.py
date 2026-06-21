from __future__ import annotations

from datetime import date, timedelta
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
    MaintenanceIn,
    PoolIn,
    ReadingIn,
    dump_model,
    model_field_names,
    validate_model,
)

templates = Jinja2Templates(directory=str(Path(__file__).parents[1] / "templates"))
templates.env.filters["num"] = services.humanize_number
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
def dashboard(request: Request, conn: db.Connection = Depends(get_db)):
    pool_id = _pool_id()
    snapshot = services.build_snapshot(conn, pool_id)
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"title": "Dashboard", "snapshot": snapshot},
    )


@router.get("/readings/new")
def new_reading(request: Request, conn: db.Connection = Depends(get_db)):
    pool_id = _pool_id()
    latest = db.latest_reading(conn, pool_id)
    return templates.TemplateResponse(
        request=request,
        name="reading_form.html",
        context={"title": "New reading", "pool_id": pool_id, "latest": latest},
    )


@router.post("/readings/new")
async def save_reading(request: Request, conn: db.Connection = Depends(get_db)):
    pool_id = _pool_id()
    form = _empty_to_none(await _form_data(request))
    try:
        reading = validate_model(ReadingIn, form)
        db.create_reading(conn, pool_id, dump_model(reading, exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse("/", status_code=303)


def _form_update_payload(model, drop: tuple[str, ...], keep_if_set: tuple[str, ...]) -> dict:
    """Turn an HTML edit-form model into a full-replace update payload.

    Drops server-computed fields and timestamp fields the user left blank so
    they keep their stored values instead of being nulled or regenerated.
    """
    payload = dump_model(model)
    for key in drop:
        payload.pop(key, None)
    for key in keep_if_set:
        if payload.get(key) is None:
            payload.pop(key, None)
    return payload


@router.get("/readings/{reading_id}/edit")
def edit_reading(reading_id: str, request: Request, conn: db.Connection = Depends(get_db)):
    pool_id = _pool_id()
    pool = db.get_pool(conn, pool_id)
    reading = db.get_reading(conn, reading_id)
    if not pool or not reading or reading["pool_id"] != pool_id:
        raise HTTPException(status_code=404, detail=f"reading not found: {reading_id}")
    reading["tested_at_local"] = db.local_timestamp(
        reading.get("tested_at"), pool.get("timezone") or "UTC"
    )
    return templates.TemplateResponse(
        request=request,
        name="reading_form.html",
        context={
            "title": "Edit reading",
            "form_title": "Edit Reading",
            "form_action": f"/readings/{reading_id}/edit",
            "reading": reading,
        },
    )


@router.post("/readings/{reading_id}/edit")
async def save_reading_edit(
    reading_id: str,
    request: Request,
    conn: db.Connection = Depends(get_db),
):
    pool_id = _pool_id()
    form = _empty_to_none(await _form_data(request))
    try:
        reading = validate_model(ReadingIn, form)
        payload = _form_update_payload(
            reading, drop=("csi", "tc", "source"), keep_if_set=("tested_at",)
        )
        db.update_reading(conn, pool_id, reading_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"not found: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse("/history", status_code=303)


@router.post("/readings/{reading_id}/delete")
def delete_reading_page(reading_id: str, conn: db.Connection = Depends(get_db)):
    pool_id = _pool_id()
    try:
        db.delete_reading(conn, pool_id, reading_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"not found: {exc.args[0]}") from exc
    return RedirectResponse("/history", status_code=303)


@router.get("/additions/new")
def new_addition(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="addition_form.html",
        context={"title": "New addition"},
    )


@router.post("/additions/new")
async def save_addition(request: Request, conn: db.Connection = Depends(get_db)):
    pool_id = _pool_id()
    form = _empty_to_none(await _form_data(request))
    try:
        addition = validate_model(AdditionIn, form)
        db.create_addition(conn, pool_id, dump_model(addition, exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse("/history", status_code=303)


@router.get("/additions/{addition_id}/edit")
def edit_addition(addition_id: str, request: Request, conn: db.Connection = Depends(get_db)):
    pool_id = _pool_id()
    pool = db.get_pool(conn, pool_id)
    addition = db.get_addition(conn, addition_id)
    if not pool or not addition or addition["pool_id"] != pool_id:
        raise HTTPException(status_code=404, detail=f"addition not found: {addition_id}")
    addition["added_at_local"] = db.local_timestamp(
        addition.get("added_at"), pool.get("timezone") or "UTC"
    )
    return templates.TemplateResponse(
        request=request,
        name="addition_form.html",
        context={
            "title": "Edit addition",
            "form_title": "Edit Addition",
            "form_action": f"/additions/{addition_id}/edit",
            "addition": addition,
        },
    )


@router.post("/additions/{addition_id}/edit")
async def save_addition_edit(
    addition_id: str,
    request: Request,
    conn: db.Connection = Depends(get_db),
):
    pool_id = _pool_id()
    form = _empty_to_none(await _form_data(request))
    try:
        addition = validate_model(AdditionIn, form)
        payload = _form_update_payload(
            addition, drop=("linked_reading_id",), keep_if_set=("added_at",)
        )
        db.update_addition(conn, pool_id, addition_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"not found: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse("/history", status_code=303)


@router.post("/additions/{addition_id}/delete")
def delete_addition_page(addition_id: str, conn: db.Connection = Depends(get_db)):
    pool_id = _pool_id()
    try:
        db.delete_addition(conn, pool_id, addition_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"not found: {exc.args[0]}") from exc
    return RedirectResponse("/history", status_code=303)


@router.get("/maintenance/new")
def new_maintenance(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="maintenance_form.html",
        context={"title": "Log maintenance"},
    )


@router.post("/maintenance/new")
async def save_maintenance(request: Request, conn: db.Connection = Depends(get_db)):
    pool_id = _pool_id()
    form = _empty_to_none(await _form_data(request))
    try:
        event = validate_model(MaintenanceIn, form)
        db.create_maintenance(conn, pool_id, dump_model(event, exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse("/history", status_code=303)


@router.get("/maintenance/{event_id}/edit")
def edit_maintenance(event_id: str, request: Request, conn: db.Connection = Depends(get_db)):
    pool_id = _pool_id()
    pool = db.get_pool(conn, pool_id)
    event = db.get_maintenance(conn, event_id)
    if not pool or not event or event["pool_id"] != pool_id:
        raise HTTPException(status_code=404, detail=f"maintenance event not found: {event_id}")
    event["event_at_local"] = db.local_timestamp(
        event.get("event_at"), pool.get("timezone") or "UTC"
    )
    return templates.TemplateResponse(
        request=request,
        name="maintenance_form.html",
        context={
            "title": "Edit maintenance",
            "form_title": "Edit Maintenance",
            "form_action": f"/maintenance/{event_id}/edit",
            "event": event,
        },
    )


@router.post("/maintenance/{event_id}/edit")
async def save_maintenance_edit(
    event_id: str,
    request: Request,
    conn: db.Connection = Depends(get_db),
):
    pool_id = _pool_id()
    form = _empty_to_none(await _form_data(request))
    try:
        event = validate_model(MaintenanceIn, form)
        payload = _form_update_payload(event, drop=(), keep_if_set=("event_at",))
        db.update_maintenance(conn, pool_id, event_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"not found: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse("/history", status_code=303)


@router.post("/maintenance/{event_id}/delete")
def delete_maintenance_page(event_id: str, conn: db.Connection = Depends(get_db)):
    pool_id = _pool_id()
    try:
        db.delete_maintenance(conn, pool_id, event_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"not found: {exc.args[0]}") from exc
    return RedirectResponse("/history", status_code=303)


def _history_utc_bounds(
    start: str | None,
    end: str | None,
    timezone_name: str,
) -> tuple[str | None, str | None]:
    try:
        start_utc = None
        if start:
            start_day = date.fromisoformat(start)
            start_utc = db.normalize_timestamp(f"{start_day.isoformat()}T00:00:00", timezone_name)

        end_utc = None
        if end:
            end_day = date.fromisoformat(end) + timedelta(days=1)
            end_utc = db.normalize_timestamp(f"{end_day.isoformat()}T00:00:00", timezone_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return start_utc, end_utc


@router.get("/history")
def history(
    request: Request,
    record: str = "all",
    start: str | None = None,
    end: str | None = None,
    conn: db.Connection = Depends(get_db),
):
    pool_id = _pool_id()
    pool = db.get_pool(conn, pool_id)
    timezone_name = pool.get("timezone") if pool else "UTC"
    start_utc, end_utc = _history_utc_bounds(start, end, timezone_name)

    readings = db.list_readings(conn, pool_id, start_utc=start_utc, end_utc=end_utc)
    for row in readings:
        row["tested_at_local"] = db.local_timestamp(row.get("tested_at"), timezone_name)
    additions = db.list_additions(conn, pool_id, start_utc=start_utc, end_utc=end_utc)
    for row in additions:
        row["added_at_local"] = db.local_timestamp(row.get("added_at"), timezone_name)
    maintenance = db.list_maintenance(conn, pool_id, start_utc=start_utc, end_utc=end_utc)
    for row in maintenance:
        row["event_at_local"] = db.local_timestamp(row.get("event_at"), timezone_name)

    if record not in {"all", "readings", "additions", "maintenance"}:
        record = "all"

    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={
            "title": "History",
            "pool_id": pool_id,
            "record": record,
            "start": start,
            "end": end,
            "readings": readings if record in {"all", "readings"} else [],
            "additions": additions if record in {"all", "additions"} else [],
            "maintenance": maintenance if record in {"all", "maintenance"} else [],
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
    product: str | None = None,
    ta: float | None = None,
    cya: float | None = None,
    borates: float | None = None,
    cell_lbs_per_day: float | None = None,
    pump_hours: float | None = None,
    conn: db.Connection = Depends(get_db),
):
    pool_id = _pool_id()
    pool = db.get_pool(conn, pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail=f"pool not found: {pool_id}")

    values = {
        "current": current,
        "target": target,
        "pool_gallons": pool_gallons,
        "strength": strength,
        "product": product,
        "ta": ta,
        "cya": cya,
        "borates": borates,
        "cell_lbs_per_day": cell_lbs_per_day,
        "pump_hours": pump_hours,
    }
    # Only attempt a calculation once the goal's primary inputs are filled in;
    # anything still missing surfaces as an inline form error, not a 400 page.
    ready = {
        "slam_fc": current is not None,
        "swg_runtime": target is not None or cell_lbs_per_day is not None,
    }.get(goal, current is not None and target is not None)

    result = None
    error = None
    if ready:
        try:
            result = services.calculate_goal(pool, goal, values)
        except ValueError as exc:
            error = str(exc)

    return templates.TemplateResponse(
        request=request,
        name="calculator.html",
        context={
            "title": "Calculator",
            "pool": pool,
            "goal": goal,
            "result": result,
            "error": error,
            **values,
        },
    )


@router.get("/settings")
def settings_page(request: Request, conn: db.Connection = Depends(get_db)):
    pool_id = _pool_id()
    pool = db.get_pool(conn, pool_id)
    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={"title": "Settings", "pool": pool},
    )


@router.post("/settings")
async def save_settings(request: Request, conn: db.Connection = Depends(get_db)):
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
    conn: db.Connection = Depends(get_db),
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
        request=request,
        name="share.html",
        context={"title": "Share", "snapshot": snapshot},
    )
