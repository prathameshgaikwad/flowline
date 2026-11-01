from __future__ import annotations

from collections.abc import Iterable

from ezdxf import bbox as ezbbox

from core.geometry import Point
from core.models import DetectedFixture, FixtureType, Room
from core.plumbing_zones import fixture_hint_from_name

MAX_BLOCK_DEPTH = 6
FIXTURE_LAYER_TOKENS = ("sanitary", "fixture", "plumbing")
FIXTURE_ORDER = {
    FixtureType.WC: 0,
    FixtureType.BASIN: 1,
    FixtureType.SHOWER: 2,
    FixtureType.FLOOR_DRAIN: 3,
    FixtureType.KITCHEN_SINK: 4,
}


def detect_fixtures(entities: Iterable, scale, rooms: list[Room]) -> list[DetectedFixture]:
    fixtures: list[DetectedFixture] = []
    sanitary_rooms: set[str] = set()

    def walk(items: Iterable, inherited_layer: str = "", depth: int = 0) -> None:
        for entity in items:
            if entity.dxftype().upper() != "INSERT":
                continue
            raw_layer = str(entity.dxf.get("layer", "0"))
            layer = inherited_layer if raw_layer in ("", "0") else raw_layer
            name = str(entity.dxf.get("name", ""))
            try:
                children = list(entity.virtual_entities())
            except Exception:
                continue
            direct = [
                child
                for child in children
                if child.dxftype().upper() != "INSERT"
            ]
            hint = fixture_hint_from_name(name, layer)
            fixture_layer = _is_fixture_layer(layer)
            classified = False
            if direct and (fixture_layer or hint is not None):
                extent = ezbbox.extents(direct, fast=True)
                if getattr(extent, "has_data", True):
                    width_units = extent.extmax.x - extent.extmin.x
                    depth_units = extent.extmax.y - extent.extmin.y
                    width_mm = scale.to_mm(width_units)
                    depth_mm = scale.to_mm(depth_units)
                    center = Point(
                        x=scale.to_mm((extent.extmin.x + extent.extmax.x) / 2),
                        y=scale.to_mm((extent.extmin.y + extent.extmax.y) / 2),
                    )
                    room = _room_for_point(center, rooms)
                    if room is not None:
                        sanitary_rooms.add(room.id)
                    fixture_type, confidence, source = _classify(
                        hint,
                        width_mm,
                        depth_mm,
                        room,
                    )
                    if fixture_type is not None:
                        classified = True
                        fixtures.append(
                            DetectedFixture(
                                id=f"F-{len(fixtures) + 1:02d}-{fixture_type.value}",
                                type=fixture_type,
                                room_id=room.id if room is not None else None,
                                position=center,
                                width_mm=width_mm,
                                depth_mm=depth_mm,
                                rotation_deg=_rotation_for_room(center, room),
                                block_name=name,
                                layer=layer,
                                source=source,
                                confidence=confidence,
                            )
                        )
            if not classified and depth < MAX_BLOCK_DEPTH:
                walk(children, layer, depth + 1)

    walk(entities)
    for room in rooms:
        if room.id in sanitary_rooms:
            room.has_sanitaryware = True
        detected = [
            FIXTURE_ORDER[fixture.type]
            for fixture in fixtures
            if fixture.room_id == room.id
        ]
        if not detected:
            continue
        types = list(room.fixture_hints)
        types.extend(
            fixture.type
            for fixture in fixtures
            if fixture.room_id == room.id
        )
        unique = list(dict.fromkeys(types))
        room.fixture_hints = sorted(unique, key=lambda item: FIXTURE_ORDER.get(item, 99))
    return fixtures


def _is_fixture_layer(layer: str) -> bool:
    lowered = layer.lower()
    return any(token in lowered for token in FIXTURE_LAYER_TOKENS)


def _room_for_point(point: Point, rooms: list[Room]) -> Room | None:
    matches = [room for room in rooms if room.contains(point)]
    if not matches:
        return None
    return min(matches, key=lambda room: room.area_mm2)


def _rotation_for_room(point: Point, room: Room | None) -> float:
    if room is None:
        return 0.0
    box = room.bbox
    distances = {
        "bottom": point.y - box.miny,
        "top": box.maxy - point.y,
        "left": point.x - box.minx,
        "right": box.maxx - point.x,
    }
    wall = min(distances, key=distances.get)
    return {"bottom": 0.0, "top": 180.0, "left": 270.0, "right": 90.0}[wall]


def _classify(
    hint: FixtureType | None,
    width_mm: float,
    depth_mm: float,
    room: Room | None,
) -> tuple[FixtureType | None, float, str]:
    if hint is not None:
        return hint, 0.95, "block_name"
    short = min(width_mm, depth_mm)
    long = max(width_mm, depth_mm)
    if short <= 0 or long <= 0:
        return None, 0.0, "geometry"
    area_m2 = width_mm * depth_mm / 1_000_000.0
    if short <= 220 and area_m2 <= 0.05:
        return FixtureType.FLOOR_DRAIN, 0.82, "geometry"
    if short >= 700 and long <= 1600 and long / short <= 1.6:
        return FixtureType.SHOWER, 0.78, "geometry"
    if 550 <= long <= 900 and 450 <= short <= 700 and long / short <= 1.7:
        return FixtureType.WC, 0.76, "geometry"
    if 250 <= short <= 390 and 300 <= long <= 750:
        return FixtureType.BASIN, 0.72, "geometry"
    if (
        room is not None
        and room.plumbing_role.value == "kitchen"
        and 400 <= long <= 1000
        and 300 <= short <= 700
    ):
        return FixtureType.KITCHEN_SINK, 0.7, "geometry"
    if 1400 <= long <= 2100 and 650 <= short <= 950 and long / short <= 2.6:
        return FixtureType.SHOWER, 0.62, "geometry"
    return None, 0.0, "geometry"
