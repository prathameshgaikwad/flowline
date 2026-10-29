from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Units(str, Enum):
    MILLIMETERS = "mm"
    CENTIMETERS = "cm"
    METERS = "m"
    INCHES = "in"
    FEET = "ft"
    UNITLESS = "unitless"


@dataclass(frozen=True)
class UnitScale:
    units: Units
    mm_per_unit: float
    warnings: tuple[str, ...] = ()

    def to_mm(self, value: float) -> float:
        return float(value) * self.mm_per_unit

    def from_mm(self, value: float) -> float:
        return float(value) / self.mm_per_unit


_KNOWN: dict[int, tuple[Units, float]] = {
    1: (Units.INCHES, 25.4),
    2: (Units.FEET, 304.8),
    4: (Units.MILLIMETERS, 1.0),
    5: (Units.CENTIMETERS, 10.0),
    6: (Units.METERS, 1000.0),
}


def unit_scale(insunits: int | None) -> UnitScale:
    if insunits in _KNOWN:
        units, scale = _KNOWN[int(insunits)]
        return UnitScale(units=units, mm_per_unit=scale)
    if insunits in (0, None):
        return UnitScale(
            units=Units.UNITLESS,
            mm_per_unit=1.0,
            warnings=("Drawing has no units; Flowline assumed millimetres.",),
        )
    return UnitScale(
        units=Units.UNITLESS,
        mm_per_unit=1.0,
        warnings=(f"Unsupported DXF units code {insunits}; Flowline assumed millimetres.",),
    )
