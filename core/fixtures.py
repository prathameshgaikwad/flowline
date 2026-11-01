from __future__ import annotations

from dataclasses import dataclass

from core.geometry import Point
from core.models import Fixture, FixtureType, System


@dataclass(frozen=True)
class FixtureConnections:
    cold: Point | None
    hot: Point | None
    drain: Point
    vent: Point | None


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


def connections_for(fixture: Fixture) -> FixtureConnections:
    rotation = int(round(fixture.rotation_deg)) % 360
    if rotation == 0:
        back, tangent = (0.0, -1.0), (1.0, 0.0)
    elif rotation == 180:
        back, tangent = (0.0, 1.0), (-1.0, 0.0)
    elif rotation == 90:
        back, tangent = (1.0, 0.0), (0.0, 1.0)
    else:
        back, tangent = (-1.0, 0.0), (0.0, -1.0)

    half_width = fixture.width_mm / 2
    half_depth = fixture.depth_mm / 2

    def point(tangent_offset: float, back_offset: float) -> Point:
        return Point(
            x=fixture.position.x + tangent[0] * tangent_offset + back[0] * back_offset,
            y=fixture.position.y + tangent[1] * tangent_offset + back[1] * back_offset,
        )

    drain = point(0.0, -half_depth * 0.35)
    vent = point(half_width * 0.26, -half_depth * 0.2)
    if fixture.type == FixtureType.FLOOR_DRAIN:
        return FixtureConnections(cold=None, hot=None, drain=fixture.position, vent=None)
    if fixture.type == FixtureType.WC:
        return FixtureConnections(
            cold=point(-half_width * 0.16, -half_depth * 0.55),
            hot=None,
            drain=drain,
            vent=vent,
        )
    return FixtureConnections(
        cold=point(-half_width * 0.2, -half_depth * 0.5),
        hot=point(half_width * 0.2, -half_depth * 0.5),
        drain=drain,
        vent=vent,
    )


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
