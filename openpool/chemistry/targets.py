from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FcCyaTarget:
    cya: int
    minimum: float
    target_low: float
    target_high: float
    slam: float
    sanitizer: str
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "cya": self.cya,
            "minimum": self.minimum,
            "targetLow": self.target_low,
            "targetHigh": self.target_high,
            "slam": self.slam,
            "sanitizer": self.sanitizer,
            "warnings": list(self.warnings),
        }


LIQUID_CHLORINE_TARGETS = {
    20: {"minimum": 2, "target_low": 3, "target_high": 5, "slam": 10},
    30: {"minimum": 2, "target_low": 4, "target_high": 6, "slam": 12},
    40: {"minimum": 3, "target_low": 5, "target_high": 7, "slam": 16},
    50: {"minimum": 4, "target_low": 6, "target_high": 8, "slam": 20},
    60: {"minimum": 5, "target_low": 7, "target_high": 9, "slam": 24},
    70: {"minimum": 5, "target_low": 8, "target_high": 10, "slam": 28},
    80: {"minimum": 6, "target_low": 9, "target_high": 11, "slam": 31},
    90: {"minimum": 7, "target_low": 10, "target_high": 12, "slam": 35},
    100: {"minimum": 7, "target_low": 11, "target_high": 13, "slam": 39},
}

SWG_TARGETS = {
    60: {"minimum": 3, "target_low": 4, "target_high": 5, "slam": 24},
    70: {"minimum": 3, "target_low": 5, "target_high": 6, "slam": 28},
    80: {"minimum": 4, "target_low": 6, "target_high": 7, "slam": 31},
}


def _table_for_sanitizer(sanitizer: str) -> dict[int, dict[str, float]]:
    if sanitizer.lower() in {"swg", "salt_water_generator"}:
        return SWG_TARGETS
    return LIQUID_CHLORINE_TARGETS


def round_cya_bucket(
    cya: float | None,
    sanitizer: str = "liquid_chlorine",
) -> tuple[int, tuple[str, ...]]:
    table = _table_for_sanitizer(sanitizer)
    buckets = sorted(table)
    warnings: list[str] = []

    if cya is None:
        warnings.append("No CYA reading yet; using the lowest supported target bucket.")
        return buckets[0], tuple(warnings)

    for bucket in buckets:
        if cya <= bucket:
            return bucket, tuple(warnings)

    warnings.append(
        "CYA is above the supported chart; using the highest bucket and warning instead."
    )
    return buckets[-1], tuple(warnings)


def fc_cya_targets(cya: float | None, sanitizer: str = "liquid_chlorine") -> FcCyaTarget:
    table = _table_for_sanitizer(sanitizer)
    bucket, warnings = round_cya_bucket(cya, sanitizer)
    row = table[bucket]
    return FcCyaTarget(cya=bucket, sanitizer=sanitizer, warnings=warnings, **row)
