from __future__ import annotations

from dataclasses import dataclass

from core.geometry import Point
from core.models import Fixture, FixtureType, System


@dataclass(frozen=True)
class FixtureSpec:
    type: FixtureType
    label: str
    width_mm: float
    depth_mm: float
    system: System
    india_diameter_mm: int
    us_diameter_mm: int
    min_side_mm: float = 381.0
    min_front_mm: float = 533.0
    target_side_mm: float = 450.0
    target_front_mm: float = 600.0


SPECS: dict[FixtureType, FixtureSpec] = {
    FixtureType.WC: FixtureSpec(
        type=FixtureType.WC,
        label="WC",
        width_mm=380.0,
        depth_mm=700.0,
        system=System.SOIL,
        india_diameter_mm=100,
        us_diameter_mm=76,
        target_side_mm=450.0,
        target_front_mm=600.0,
    ),
    FixtureType.BASIN: FixtureSpec(
        type=FixtureType.BASIN,
        label="BASIN",
        width_mm=550.0,
        depth_mm=450.0,
        system=System.WASTE,
        india_diameter_mm=40,
        us_diameter_mm=32,
        target_side_mm=500.0,
        target_front_mm=700.0,
    ),
    FixtureType.SHOWER: FixtureSpec(
        type=FixtureType.SHOWER,
        label="SHOWER",
        width_mm=900.0,
        depth_mm=900.0,
        system=System.WASTE,
        india_diameter_mm=50,
        us_diameter_mm=50,
        target_side_mm=450.0,
        target_front_mm=600.0,
    ),
    FixtureType.FLOOR_DRAIN: FixtureSpec(
        type=FixtureType.FLOOR_DRAIN,
        label="FD",
        width_mm=150.0,
        depth_mm=150.0,
        system=System.WASTE,
        india_diameter_mm=50,
        us_diameter_mm=50,
        min_side_mm=0.0,
        min_front_mm=0.0,
        target_side_mm=0.0,
        target_front_mm=0.0,
    ),
    FixtureType.KITCHEN_SINK: FixtureSpec(
        type=FixtureType.KITCHEN_SINK,
        label="SINK",
        width_mm=600.0,
        depth_mm=500.0,
        system=System.WASTE,
        india_diameter_mm=50,
        us_diameter_mm=50,
        target_side_mm=450.0,
        target_front_mm=700.0,
    ),
}


def spec_for(fixture_type: FixtureType | str) -> FixtureSpec:
    if isinstance(fixture_type, FixtureType):
        return SPECS[fixture_type]
    return SPECS[FixtureType(str(fixture_type))]


def make_fixture(
    fixture_id: str,
    fixture_type: FixtureType | str,
    position: Point,
    *,
    room_id: str | None = None,
    rotation_deg: float = 0.0,
    wall_id: str | None = None,
) -> Fixture:
    spec = spec_for(fixture_type)
    return Fixture(
        id=fixture_id,
        type=spec.type,
        position=position,
        rotation_deg=rotation_deg,
        width_mm=spec.width_mm,
        depth_mm=spec.depth_mm,
        room_id=room_id,
        wall_id=wall_id,
    )
