from __future__ import annotations

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    field_validator,
)

PoolSurface = Literal["plaster", "fiberglass", "vinyl"]
PoolSanitizer = Literal["liquid_chlorine", "swg", "salt_water_generator"]


def _reject_boolean_number(value: object) -> object:
    if isinstance(value, bool):
        raise ValueError("must be a number, not a boolean")
    return value


Number = Annotated[float, BeforeValidator(_reject_boolean_number)]
NonBlankString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class PoolIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = Field(None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    name: NonBlankString = "Home Pool"
    volume_gallons: Number = Field(20_000, gt=0, le=1_000_000)
    spa_volume_gallons: Number | None = Field(None, gt=0, le=1_000_000)
    surface: PoolSurface = "plaster"
    sanitizer: PoolSanitizer = "liquid_chlorine"
    unit_system: Literal["us"] = "us"
    timezone: NonBlankString = "UTC"
    default_chlorine_percent: Number = Field(10.0, ge=1, le=100)
    default_cya_target: Number = Field(40.0, ge=0, le=500)
    default_salt_target: Number = Field(3200.0, ge=0, le=50_000)
    jug_size_fl_oz: Number = Field(128.0, gt=0)
    bag_size_lbs: Number = Field(40.0, gt=0)
    share_enabled: bool = False
    share_token: str | None = None
    include_notes_in_share: bool = False
    notes: str | None = None


class PoolUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: NonBlankString | None = None
    volume_gallons: Number | None = Field(None, gt=0, le=1_000_000)
    spa_volume_gallons: Number | None = Field(None, gt=0, le=1_000_000)
    surface: PoolSurface | None = None
    sanitizer: PoolSanitizer | None = None
    unit_system: Literal["us"] | None = None
    timezone: NonBlankString | None = None
    default_chlorine_percent: Number | None = Field(None, ge=1, le=100)
    default_cya_target: Number | None = Field(None, ge=0, le=500)
    default_salt_target: Number | None = Field(None, ge=0, le=50_000)
    jug_size_fl_oz: Number | None = Field(None, gt=0)
    bag_size_lbs: Number | None = Field(None, gt=0)
    share_enabled: bool | None = None
    share_token: str | None = None
    include_notes_in_share: bool | None = None
    notes: str | None = None

    @field_validator(
        "name",
        "volume_gallons",
        "surface",
        "sanitizer",
        "unit_system",
        "timezone",
        "default_chlorine_percent",
        "default_cya_target",
        "default_salt_target",
        "jug_size_fl_oz",
        "bag_size_lbs",
        "share_enabled",
        "include_notes_in_share",
        mode="before",
    )
    @classmethod
    def required_fields_cannot_be_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("cannot be null")
        return value


class ReadingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tested_at: str | None = None
    fc: Number | None = Field(None, ge=0, le=100)
    cc: Number | None = Field(None, ge=0, le=100)
    ph: Number | None = Field(None, ge=0, le=14)
    ta: Number | None = Field(None, ge=0, le=2_000)
    ch: Number | None = Field(None, ge=0, le=2_000)
    cya: Number | None = Field(None, ge=0, le=500)
    salt: Number | None = Field(None, ge=0, le=50_000)
    borates: Number | None = Field(None, ge=0, le=200)
    water_temp_f: Number | None = Field(None, ge=32, le=120)
    filter_pressure: Number | None = Field(None, ge=0, le=100)
    source: NonBlankString = "manual"
    notes: str | None = None


class AdditionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    added_at: str | None = None
    chemical: NonBlankString
    strength_percent: Number | None = Field(None, ge=1, le=100)
    amount: Number = Field(..., gt=0, le=100_000)
    unit: NonBlankString
    reason: str | None = None
    linked_reading_id: str | None = None
    notes: str | None = None


class AdditionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    added_at: str | None = None
    chemical: NonBlankString | None = None
    strength_percent: Number | None = Field(None, ge=1, le=100)
    amount: Number | None = Field(None, gt=0, le=100_000)
    unit: NonBlankString | None = None
    reason: str | None = None
    linked_reading_id: str | None = None
    notes: str | None = None

    @field_validator("chemical", "amount", "unit", mode="before")
    @classmethod
    def required_fields_cannot_be_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("cannot be null")
        return value


class MaintenanceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_at: str | None = None
    event_type: NonBlankString
    notes: str | None = None


class MaintenanceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_at: str | None = None
    event_type: NonBlankString | None = None
    notes: str | None = None

    @field_validator("event_type", mode="before")
    @classmethod
    def event_type_cannot_be_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("cannot be null")
        return value


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
    current: Number | None = Field(None, ge=0)
    target: Number | None = Field(None, ge=0)
    pool_gallons: Number | None = Field(None, gt=0, le=1_000_000)
    strength: Number | None = Field(None, ge=1, le=100)
    strength_confirmed: StrictBool = False
    strength_product: str | None = None
    product: str | None = None
    ta: Number | None = Field(None, ge=0, le=2_000)
    cya: Number | None = Field(None, ge=0, le=500)
    borates: Number | None = Field(None, ge=0, le=200)
    cell_lbs_per_day: Number | None = Field(None, gt=0)
    pump_hours: Number | None = Field(None, gt=0, le=24)
