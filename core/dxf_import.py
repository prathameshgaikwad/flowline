from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

import ezdxf
from ezdxf.path import from_hatch
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import unary_union

from core.fixture_detect import detect_fixtures
from core.geometry import Point, bbox, distance, polygon_area
from core.layers import (
    LayerRole,
    classify_layer,
    is_room_label_text,
)
from core.models import Building, Door, DrawingEntity, FixtureType, Shaft, ShaftService
from core.plumbing_zones import fixture_hint_from_name
from core.room_detect import detect_rooms
from core.units import unit_scale

PARSER_VERSION = 6
MAX_BLOCK_DEPTH = 6
HATCH_FLATTEN_MM = 5.0
SANITARYWARE_TOKEN = "sanitaryware"
FLOOR_HATCH_TOKEN = "hatch"
ROOM_BBOX_OVERLAP_LIMIT = 0.5
MIN_FLOOR_HATCH_ROOM_M2 = 1.0
MAX_FLOOR_HATCH_ROOM_M2 = 50.0
WALL_FILL_ROOM_OVERLAP_LIMIT = 0.5
MIN_SHAFT_AREA_M2 = 0.04
MAX_SHAFT_AREA_M2 = 4.0
MIN_SHAFT_SIDE_MM = 150.0
MAX_SHAFT_SIDE_MM = 2500.0
MAX_SHAFT_ASPECT = 10.0
INFERRED_SHAFT_MAX_DISTANCE_MM = 1500.0
EXCLUDED_SHAFT_LAYER_TOKENS = (
    "wall",
    "column",
    "furniture",
    "sanitaryware",
    "door",
    "window",
    "structure",
    "parapet",
    "handrail",
    "balustrade",
    "tile",
    "floor",
    "louver",
    "dimension",
    "note",
)
SHAFT_TEXT_TOKENS = (
    "shaft",
    "duct",
    "riser",
    "chase",
    "service shaft",
    "plumbing shaft",
    "wet shaft",
    "mep shaft",
)
SHAFT_SERVICE_TOKENS: tuple[tuple[ShaftService, tuple[str, ...]], ...] = (
    (ShaftService.DRAIN, ("soil", "waste", "drain", "outlet", "stack")),
    (ShaftService.WATER, ("water", "supply", "inlet", "main", "cold", "hot")),
    (ShaftService.VENT, ("vent",)),
)


class DxfImportError(ValueError):
    """The drawing cannot be read or has no usable plan content."""


def import_dxf(path: str | Path) -> Building:
    source = Path(path)
    if not source.exists():
        raise DxfImportError(f"Drawing not found: {source}")
    try:
        doc = ezdxf.readfile(source)
    except Exception as exc:
        raise DxfImportError(f"Cannot read {source.name}: {exc}") from exc

    scale = unit_scale(doc.header.get("$INSUNITS", 0))
    msp = doc.modelspace()

    entities: list[DrawingEntity] = []
    floor_hatches: list[DrawingEntity] = []
    wall_fills: list[ShapelyPolygon] = []
    door_candidates: list[Door] = []
    shaft_candidates: list[Shaft] = []
    inferred_shafts: list[tuple[Shaft, DrawingEntity]] = []
    shaft_labels: list[tuple[str, Point]] = []
    skipped = 0

    for entity, skip_door in _iter_entities(msp):
        try:
            if entity.dxftype().upper() == "HATCH":
                hatch_items, hatch_fills = _read_hatch_entities(entity, scale)
                entities.extend(hatch_items)
                wall_fills.extend(hatch_fills)
                floor_hatches.extend(_read_floor_hatch_polygons(entity, scale))
                inferred, boundary = _read_shaft_hatch(entity, scale)
                if inferred is not None and boundary is not None:
                    inferred_shafts.append((inferred, boundary))
                continue
            item, door, shaft = _read_entity(entity, scale, detect_door=not skip_door)
        except Exception:
            skipped += 1
            continue
        if item is not None:
            entities.append(item)
            if (
                item.kind == "text"
                and item.text
                and item.position is not None
                and _is_shaft_label(item.text)
            ):
                shaft_labels.append((item.text, item.position))
        if door is not None:
            door_candidates.append(door)
        if shaft is not None:
            shaft_candidates.append(shaft)

    room_result = detect_rooms(entities)
    room_result.rooms = _drop_wall_fill_rooms(room_result.rooms, wall_fills)
    inferred_rooms = room_result.rooms
    room_result.rooms = _merge_floor_hatch_rooms(
        room_result.rooms, floor_hatches, entities
    )
    _assign_fixture_hints(room_result.rooms, entities, generic_rooms=inferred_rooms)
    detected_fixtures = detect_fixtures(msp, scale, room_result.rooms)
    warnings = list(scale.warnings) + list(room_result.warnings)
    if skipped:
        warnings.append(f"{skipped} DXF entit{'y' if skipped == 1 else 'ies'} could not be read.")

    doors = _dedupe_doors(door_candidates)
    if not doors:
        warnings.append("No door detected. Set the door position manually.")

    wet_rooms = [room for room in room_result.rooms if room.is_wet_area]
    kept_inferred = [
        (shaft, boundary)
        for shaft, boundary in inferred_shafts
        if _shaft_is_near_wet_room(shaft, wet_rooms)
    ]
    entities.extend(boundary for _, boundary in kept_inferred)
    shafts = _dedupe_shafts(
        [*shaft_candidates, *(shaft for shaft, _ in kept_inferred)]
    )
    shafts = _apply_shaft_labels(shafts, shaft_labels)
    if not shafts:
        warnings.append("No shaft detected. Set the stack position manually.")

    return Building(
        id=source.stem,
        units=scale.units.value,
        source_scale=scale.mm_per_unit,
        rooms=room_result.rooms,
        doors=doors,
        shafts=shafts,
        detected_fixtures=detected_fixtures,
        entities=entities,
        warnings=warnings,
    )


def _iter_entities(
    entities: Iterable,
    *,
    skip_door: bool = False,
    depth: int = 0,
):
    """Yield model entities, expanding block references into transformed geometry."""
    for entity in entities:
        kind = entity.dxftype().upper()
        if kind == "INSERT" and depth < MAX_BLOCK_DEPTH:
            layer = str(entity.dxf.get("layer", "0"))
            name = str(entity.dxf.get("name", ""))
            try:
                children = list(entity.virtual_entities())
            except Exception:
                children = []
            if children:
                door_insert = classify_layer(layer) == LayerRole.DOOR or "door" in name.lower()
                fixture_insert = fixture_hint_from_name(name, layer) is not None
                if door_insert or fixture_insert:
                    anchor = _entities_center(children)
                    if anchor is not None:
                        entity.dxf.insert = (anchor.x, anchor.y, 0.0)
                        entity.dxf.extrusion = (0.0, 0.0, 1.0)
                    yield entity, skip_door
                child_skip_door = skip_door or door_insert
                for child in children:
                    child_layer = str(child.dxf.get("layer", "0"))
                    if child_layer in ("", "0") and layer not in ("", "0"):
                        try:
                            child.dxf.layer = layer
                        except Exception:
                            pass
                    yield from _iter_entities(
                        [child], skip_door=child_skip_door, depth=depth + 1
                    )
                continue
        yield entity, skip_door


def _read_entity(entity, scale, *, detect_door: bool = True):
    kind = entity.dxftype().upper()
    layer = str(entity.dxf.get("layer", "0"))
    role = classify_layer(layer)
    item: DrawingEntity | None = None
    door: Door | None = None
    shaft: Shaft | None = None

    if kind == "LWPOLYLINE":
        points = [_point(p.x, p.y, scale) for p in entity.vertices_in_wcs()]
        closed = bool(entity.closed)
        item = DrawingEntity(
            kind="polyline",
            layer=layer,
            role=role.value,
            points=points,
            closed=closed,
        )
        if closed and role == LayerRole.SHAFT and len(points) >= 3:
            shaft = _shaft_from_points(points)
    elif kind == "POLYLINE":
        points = [_point(p.x, p.y, scale) for p in entity.points_in_wcs()]
        closed = bool(entity.is_closed)
        item = DrawingEntity(
            kind="polyline",
            layer=layer,
            role=role.value,
            points=points,
            closed=closed,
        )
        if closed and role == LayerRole.SHAFT and len(points) >= 3:
            shaft = _shaft_from_points(points)
    elif kind == "LINE":
        start = _point(entity.dxf.start.x, entity.dxf.start.y, scale)
        end = _point(entity.dxf.end.x, entity.dxf.end.y, scale)
        item = DrawingEntity(
            kind="line",
            layer=layer,
            role=role.value,
            points=[start, end],
        )
        length = distance(start, end)
        if detect_door and role == LayerRole.DOOR and length >= 300:
            midpoint = Point(x=(start.x + end.x) / 2, y=(start.y + end.y) / 2)
            door = Door(
                id=f"D-{round(midpoint.x)}-{round(midpoint.y)}",
                position=midpoint,
                width_mm=length,
            )
    elif kind == "CIRCLE":
        center = _wcs_point(entity, entity.dxf.center, scale)
        radius = abs(float(entity.dxf.radius)) * scale.mm_per_unit
        item = DrawingEntity(
            kind="circle",
            layer=layer,
            role=role.value,
            center=center,
            radius=radius,
        )
    elif kind == "ARC":
        center = _wcs_point(entity, entity.dxf.center, scale)
        radius = abs(float(entity.dxf.radius)) * scale.mm_per_unit
        item = DrawingEntity(
            kind="arc",
            layer=layer,
            role=role.value,
            points=_flatten_arc(entity, scale),
            center=center,
            radius=radius,
            start_angle=float(entity.dxf.start_angle),
            end_angle=float(entity.dxf.end_angle),
        )
    elif kind in ("TEXT", "MTEXT"):
        raw_text = entity.plain_text() if kind == "MTEXT" else str(entity.dxf.text)
        position = _wcs_point(entity, entity.dxf.insert, scale)
        text_role = (
            LayerRole.ROOM_LABEL.value
            if is_room_label_text(raw_text, layer)
            else role.value
        )
        item = DrawingEntity(
            kind="text",
            layer=layer,
            role=text_role,
            text=raw_text,
            position=position,
        )
    elif kind == "INSERT":
        position = _wcs_point(entity, entity.dxf.insert, scale)
        name = str(entity.dxf.name)
        item = DrawingEntity(
            kind="insert",
            layer=layer,
            role=role.value,
            position=position,
            block_name=name,
        )
        if detect_door and (
            role == LayerRole.DOOR or any(token in name.lower() for token in ("door",))
        ):
            door = Door(
                id=f"D-{round(position.x)}-{round(position.y)}",
                position=position,
                width_mm=_width_from_name(name),
            )
    return item, door, shaft


def _entities_center(entities) -> Point | None:
    xs: list[float] = []
    ys: list[float] = []
    for entity in entities:
        kind = entity.dxftype().upper()
        try:
            if kind == "LWPOLYLINE":
                points = list(entity.vertices_in_wcs())
            elif kind == "POLYLINE":
                points = list(entity.points_in_wcs())
            elif kind == "LINE":
                points = [entity.dxf.start, entity.dxf.end]
            else:
                points = []
            for point in points:
                xs.append(float(point.x))
                ys.append(float(point.y))
            if kind in ("ARC", "CIRCLE"):
                center = entity.ocs().to_wcs(entity.dxf.center)
                radius = abs(float(entity.dxf.radius))
                xs.extend([center.x - radius, center.x + radius])
                ys.extend([center.y - radius, center.y + radius])
        except Exception:
            continue
    if not xs or not ys:
        return None
    return Point(x=(min(xs) + max(xs)) / 2, y=(min(ys) + max(ys)) / 2)


def _wcs_point(entity, point, scale) -> Point:
    wcs = entity.ocs().to_wcs(point)
    return _point(wcs.x, wcs.y, scale)


def _flatten_arc(entity, scale) -> list[Point]:
    try:
        sagitta = HATCH_FLATTEN_MM / scale.mm_per_unit
        return [_point(p.x, p.y, scale) for p in entity.flattening(sagitta)]
    except Exception:
        return []


def _read_hatch_entities(entity, scale) -> tuple[list[DrawingEntity], list[ShapelyPolygon]]:
    layer = str(entity.dxf.get("layer", "0"))
    if classify_layer(layer) != LayerRole.WALL:
        return [], []
    items: list[DrawingEntity] = []
    fills: list[ShapelyPolygon] = []
    try:
        paths = list(from_hatch(entity))
    except Exception:
        return items, fills
    for path in paths:
        try:
            points = [
                _point(p.x, p.y, scale)
                for p in path.flattening(HATCH_FLATTEN_MM / scale.mm_per_unit)
            ]
        except Exception:
            continue
        if len(points) < 2:
            continue
        if path.is_closed and len(points) >= 3:
            fill = ShapelyPolygon([(point.x, point.y) for point in points])
            if not fill.is_valid:
                fill = fill.buffer(0)
            if not fill.is_empty:
                fills.append(fill)
        edge_count = len(points) if path.is_closed else len(points) - 1
        for index in range(edge_count):
            start = points[index]
            end = points[(index + 1) % len(points)]
            if start == end:
                continue
            items.append(
                DrawingEntity(
                    kind="line",
                    layer=layer,
                    role=LayerRole.WALL.value,
                    points=[start, end],
                )
            )
    return items, fills


def _drop_wall_fill_rooms(rooms, fills: list[ShapelyPolygon]):
    if not fills:
        return rooms
    union = unary_union(fills)
    kept = []
    for room in rooms:
        polygon = ShapelyPolygon([(point.x, point.y) for point in room.boundary])
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        if polygon.is_empty or polygon.area <= 0:
            continue
        overlap = polygon.intersection(union).area / polygon.area
        if overlap < WALL_FILL_ROOM_OVERLAP_LIMIT:
            kept.append(room)
    return kept


def _read_floor_hatch_polygons(entity, scale) -> list[DrawingEntity]:
    layer = str(entity.dxf.get("layer", "0"))
    lowered = layer.lower()
    if FLOOR_HATCH_TOKEN not in lowered or "wall" in lowered:
        return []
    polygons: list[DrawingEntity] = []
    try:
        paths = list(from_hatch(entity))
    except Exception:
        return polygons
    for path in paths:
        if not path.is_closed:
            continue
        try:
            points = [
                _point(p.x, p.y, scale)
                for p in path.flattening(HATCH_FLATTEN_MM / scale.mm_per_unit)
            ]
        except Exception:
            continue
        if len(points) < 4:
            continue
        area_m2 = polygon_area(points) / 1_000_000.0
        if not MIN_FLOOR_HATCH_ROOM_M2 <= area_m2 <= MAX_FLOOR_HATCH_ROOM_M2:
            continue
        polygons.append(
            DrawingEntity(
                kind="polyline",
                layer=layer,
                role=LayerRole.ROOM.value,
                points=points,
                closed=True,
            )
        )
    return polygons


def _read_shaft_hatch(
    entity, scale
) -> tuple[Shaft | None, DrawingEntity | None]:
    layer = str(entity.dxf.get("layer", "0"))
    if _is_excluded_shaft_layer(layer):
        return None, None
    explicit_hatch_layer = any(
        token in layer.lower() for token in ("shaft", "duct", "riser", "chase")
    )
    if not entity.dxf.get("solid_fill") and not explicit_hatch_layer:
        return None, None
    try:
        paths = list(from_hatch(entity))
    except Exception:
        return None, None
    for path in paths:
        if not path.is_closed:
            continue
        try:
            points = [
                _point(p.x, p.y, scale)
                for p in path.flattening(HATCH_FLATTEN_MM / scale.mm_per_unit)
            ]
        except Exception:
            continue
        if len(points) < 4:
            continue
        area_m2 = polygon_area(points) / 1_000_000.0
        box = bbox(points)
        short = min(box.width, box.height)
        long = max(box.width, box.height)
        if not MIN_SHAFT_AREA_M2 <= area_m2 <= MAX_SHAFT_AREA_M2:
            continue
        if short < MIN_SHAFT_SIDE_MM or long > MAX_SHAFT_SIDE_MM:
            continue
        if short <= 0 or long / short > MAX_SHAFT_ASPECT:
            continue
        shaft = _shaft_from_points(points)
        shaft.source = "inferred_hatch"
        shaft.confidence = 0.65
        shaft.services = _services_from_text(layer)
        boundary = DrawingEntity(
            kind="polyline",
            layer=layer,
            role=LayerRole.SHAFT.value,
            points=points,
            closed=True,
        )
        return shaft, boundary
    return None, None


def _is_excluded_shaft_layer(layer: str) -> bool:
    lowered = layer.lower()
    return any(token in lowered for token in EXCLUDED_SHAFT_LAYER_TOKENS)


def _is_shaft_label(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in SHAFT_TEXT_TOKENS)


def _services_from_text(value: str) -> list[ShaftService]:
    lowered = value.lower()
    services = [
        service
        for service, tokens in SHAFT_SERVICE_TOKENS
        if any(token in lowered for token in tokens)
    ]
    if services:
        return services
    return [ShaftService.DRAIN, ShaftService.WATER, ShaftService.VENT]


def _apply_shaft_labels(
    shafts: list[Shaft], labels: list[tuple[str, Point]]
) -> list[Shaft]:
    result = list(shafts)
    for text, position in labels:
        target = next(
            (
                shaft
                for shaft in result
                if shaft.bbox.contains(position, tolerance=500)
            ),
            None,
        )
        if target is None and result:
            target = min(result, key=lambda shaft: distance(shaft.position, position))
            if distance(target.position, position) > 1500:
                target = None
        if target is None:
            target = Shaft(
                id=f"S-{round(position.x)}-{round(position.y)}",
                position=position,
                width_mm=300.0,
                depth_mm=300.0,
                source="label",
                confidence=1.0,
            )
            result.append(target)
        target.name = text.strip()
        target.services = _services_from_text(text)
    return result


def _shaft_is_near_wet_room(shaft: Shaft, rooms: list) -> bool:
    if not rooms:
        return False
    shaft_box = shaft.bbox
    for room in rooms:
        room_box = room.bbox
        dx = max(
            0.0,
            max(shaft_box.minx - room_box.maxx, room_box.minx - shaft_box.maxx),
        )
        dy = max(
            0.0,
            max(shaft_box.miny - room_box.maxy, room_box.miny - shaft_box.maxy),
        )
        if (dx * dx + dy * dy) ** 0.5 <= INFERRED_SHAFT_MAX_DISTANCE_MM:
            return True
    return False


def _merge_floor_hatch_rooms(rooms, floor_hatches, entities):
    if not floor_hatches:
        return rooms
    anchors = [
        anchor
        for entity in entities
        if SANITARYWARE_TOKEN in entity.layer.lower()
        if (anchor := _entity_anchor(entity)) is not None
    ]
    if not anchors:
        return rooms
    candidates = detect_rooms(floor_hatches).rooms
    merged = list(rooms)
    for candidate in candidates:
        if not any(candidate.contains(anchor) for anchor in anchors):
            continue
        if any(_room_overlap(candidate, room) >= ROOM_BBOX_OVERLAP_LIMIT for room in merged):
            continue
        merged.append(candidate)
    for index, room in enumerate(merged, start=1):
        room.id = f"R-{index:02d}"
    return merged


def _room_overlap(first, second) -> float:
    a = first.bbox
    b = second.bbox
    width = max(0.0, min(a.maxx, b.maxx) - max(a.minx, b.minx))
    height = max(0.0, min(a.maxy, b.maxy) - max(a.miny, b.miny))
    intersection = width * height
    smaller = min(a.width * a.height, b.width * b.height)
    if smaller <= 0:
        return 0.0
    return intersection / smaller


def _shaft_from_points(points: list[Point]) -> Shaft:
    box = bbox(points)
    return Shaft(
        id=f"S-{round(box.center.x)}-{round(box.center.y)}",
        position=box.center,
        width_mm=box.width,
        depth_mm=box.height,
    )


def _assign_fixture_hints(rooms, entities: list[DrawingEntity], *, generic_rooms=None) -> None:
    for entity in entities:
        if entity.kind != "insert" or entity.position is None:
            continue
        hint = fixture_hint_from_name(entity.block_name, entity.layer)
        if hint is None:
            continue
        for room in rooms:
            if room.contains(entity.position):
                if hint not in room.fixture_hints:
                    room.fixture_hints.append(hint)
                break

    generic_ids = None if generic_rooms is None else {id(room) for room in generic_rooms}
    for entity in entities:
        if SANITARYWARE_TOKEN not in entity.layer.lower():
            continue
        anchor = _entity_anchor(entity)
        if anchor is None:
            continue
        for room in rooms:
            if generic_ids is not None and id(room) not in generic_ids:
                continue
            if room.name is not None or not room.contains(anchor):
                continue
            if FixtureType.KITCHEN_SINK not in room.fixture_hints:
                room.has_sanitaryware = True
            break


def _entity_anchor(entity: DrawingEntity) -> Point | None:
    if entity.points:
        return bbox(entity.points).center
    if entity.center is not None:
        return entity.center
    return entity.position


def _dedupe_doors(doors: list[Door]) -> list[Door]:
    result: list[Door] = []
    for door in doors:
        if any(distance(door.position, existing.position) < 100 for existing in result):
            continue
        result.append(door)
    return result


def _dedupe_shafts(shafts: list[Shaft]) -> list[Shaft]:
    result: list[Shaft] = []
    for shaft in shafts:
        if any(distance(shaft.position, existing.position) < 100 for existing in result):
            continue
        result.append(shaft)
    return result


def _width_from_name(name: str) -> float:
    match = re.search(r"(\d{3,4})", name)
    return float(match.group(1)) if match else 900.0


def _point(x: float, y: float, scale) -> Point:
    return Point(x=scale.to_mm(float(x)), y=scale.to_mm(float(y)))
