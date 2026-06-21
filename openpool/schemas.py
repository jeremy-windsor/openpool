from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PoolIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    name: str = "Home Pool"
    volume_gallons: float = Field(20_000, gt=0)
    spa_volume_gallons: float | None = Field(None, gt=0)
    surface: str = "plaster"
    sanitizer: str = "liquid_chlorine"
    unit_system: Literal["us", "metric"] = "us"
    timezone: str = "UTC"
    default_chlorine_percent: float = Field(10.0, gt=0)
    default_cya_target: float = Field(40.0, ge=0)
    default_salt_target: float = Field(3200.0, ge=0)
    jug_size_fl_oz: float = Field(128.0, gt=0)
    bag_size_lbs: float = Field(40.0, gt=0)
    share_enabled: bool = False
    share_token: str | None = None
    include_notes_in_share: bool = False
    notes: str | None = None


class PoolUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    volume_gallons: float | None = Field(None, gt=0)
    spa_volume_gallons: float | None = Field(None, gt=0)
    surface: str | None = None
    sanitizer: str | None = None
    unit_system: Literal["us", "metric"] | None = None
    timezone: str | None = None
    default_chlorine_percent: float | None = Field(None, gt=0)
    default_cya_target: float | None = Field(None, ge=0)
    default_salt_target: float | None = Field(None, ge=0)
    jug_size_fl_oz: float | None = Field(None, gt=0)
    bag_size_lbs: float | None = Field(None, gt=0)
    share_enabled: bool | None = None
    share_token: str | None = None
    include_notes_in_share: bool | None = None
    notes: str | None = None


class ReadingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tested_at: str | None = None
    fc: float | None = Field(None, ge=0)
    cc: float | None = Field(None, ge=0)
    tc: float | None = Field(None, ge=0)
    ph: float | None = Field(None, ge=0, le=14)
    ta: float | None = Field(None, ge=0)
    ch: float | None = Field(None, ge=0)
    cya: float | None = Field(None, ge=0)
    salt: float | None = Field(None, ge=0)
    borates: float | None = Field(None, ge=0)
    water_temp_f: float | None = None
    filter_pressure: float | None = Field(None, ge=0)
    csi: float | None = None
    source: str = "manual"
    notes: str | None = None


class AdditionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    added_at: str | None = None
    chemical: str
    strength_percent: float | None = Field(None, gt=0)
    amount: float = Field(..., gt=0)
    unit: str
    reason: str | None = None
    linked_reading_id: str | None = None
    notes: str | None = None


class AdditionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    added_at: str | None = None
    chemical: str | None = None
    strength_percent: float | None = Field(None, gt=0)
    amount: float | None = Field(None, gt=0)
    unit: str | None = None
    reason: str | None = None
    linked_reading_id: str | None = None
    notes: str | None = None


class MaintenanceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_at: str | None = None
    event_type: str
    notes: str | None = None


class MaintenanceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_at: str | None = None
    event_type: str | None = None
    notes: str | None = None


class CalculationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: Literal[
        "raise_fc",
        "slam_fc",
        "raise_cya",
        "raise_salt",
        "raise_ch",
        "raise_ta",
        "lower_ph",
        "raise_ph",
        "lower_by_dilution",
        "swg_runtime",
    ]
    current: float | None = Field(None, ge=0)
    target: float | None = Field(None, ge=0)
    pool_gallons: float | None = Field(None, gt=0)
    strength: float | None = Field(None, gt=0)
    product: str | None = None
    ta: float | None = Field(None, ge=0)
    cya: float | None = Field(None, ge=0)
    borates: float | None = Field(None, ge=0)
    cell_lbs_per_day: float | None = Field(None, gt=0)
    pump_hours: float | None = Field(None, gt=0, le=24)


def validate_model(model_class, data: dict):
    if hasattr(model_class, "model_validate"):
        return model_class.model_validate(data)
    return model_class(**data)


def dump_model(model: BaseModel, **kwargs) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump(**kwargs)

    allowed = {"exclude_none", "exclude_unset", "by_alias", "exclude_defaults"}
    return model.dict(**{key: value for key, value in kwargs.items() if key in allowed})


def model_field_names(model_class) -> set[str]:
    if hasattr(model_class, "model_fields"):
        return set(model_class.model_fields)
    return set(model_class.__fields__)
