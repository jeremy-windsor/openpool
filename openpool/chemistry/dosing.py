from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Dose:
    chemical: str
    amount: float
    unit: str
    secondary: dict[str, float] = field(default_factory=dict)
    # Approximate side effects on other readings, keyed by reading name with a
    # signed ppm delta (for example {"cya": 6.1} or {"ta": -3.9}).
    effects: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    formula: str | None = None
    source_note: str | None = None
    assumptions: list[str] = field(default_factory=list)
    confidence: str = "high"

    def to_dict(self) -> dict[str, object]:
        return {
            "chemical": self.chemical,
            "amount": self.amount,
            "unit": self.unit,
            "secondary": self.secondary,
            "effects": self.effects,
            "warnings": self.warnings,
            "formula": self.formula,
            "sourceNote": self.source_note,
            "assumptions": self.assumptions,
            "confidence": self.confidence,
        }
