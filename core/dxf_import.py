from __future__ import annotations

import re
from pathlib import Path

import ezdxf

from core.geometry import Point, bbox, distance, point_in_polygon, polygon_area
from core.models import Building, Door, DrawingEntity, Room, Shaft
from core.units import unit_scale

ROOM_LAYER_TOKENS = ("room", "space", "area")
DOOR_LAYER_TOKENS = ("door",)
SHAFT_LAYER_TOKENS = ("shaft", "duct", "riser")


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
    closed_polylines: list[tuple[list[Point], str]] = []
    texts: list[tuple[str, Point]] = []
    door_candidates: list[Door] = []
    shaft_candidates: list[Shaft] = []

    for entity in msp:
        try:
            item, polyline, text, door, shaft = _read_entity(entity, scale)
        except Exception:
            continue
        if item is not None:
            entities.append(item)
        if polyline is not None:
            closed_polylines.append(polyline)
        if text is not None:
            texts.append(text)
        if door is not None:
            door_candidates.append(door)
        if shaft is not None:
            shaft_candidates.append(shaft)

    warnings = list(scale.warnings)
    rooms = _detect_rooms(closed_polylines, texts)
    if not rooms:
        warnings.append(
            "No closed room boundaries found. Draw a closed polyline on A-ROOM "
            "or use the manual rectangle fallback."
        )

    doors = _dedupe_doors(door_candidates)
    if not doors:
        warnings.append("No door detected. Set the door position manually.")

    shafts = _dedupe_shafts(shaft_candidates)
    if not shafts:
        warnings.append("No shaft detected. Set the stack position manually.")

    return Building(
        id=source.stem,
        units=scale.units.value,
        source_scale=scale.mm_per_unit,
        rooms=rooms,
        doors=doors,
        shafts=shafts,
        entities=entities,
        warnings=warnings,
    )


def _read_entity(entity, scale):
    kind = entity.dxftype().upper()
    layer = str(entity.dxf.get("layer", "0"))
    item: DrawingEntity | None = None
    polyline: tuple[list[Point], str] | None = None
    text: tuple[str, Point] | None = None
    door: Door | None = None
    shaft: Shaft | None = None

    if kind == "LWPOLYLINE":
        points = [_point(x, y, scale) for x, y in entity.get_points("xy")]
        closed = bool(entity.closed)
        item = DrawingEntity(kind="polyline", layer=layer, points=points)
        if closed and len(points) >= 3:
            polyline = (points, layer)
            if any(token in layer.lower() for token in SHAFT_LAYER_TOKENS):
                box = bbox(points)
                shaft = Shaft(
                    id=f"S-{round(box.center.x)}-{round(box.center.y)}",
                    position=box.center,
                    width_mm=box.width,
                    depth_mm=box.height,
                )
    elif kind == "POLYLINE":
        raw = list(entity.points())
        points = [_point(p.x, p.y, scale) for p in raw]
        closed = bool(entity.is_closed)
        item = DrawingEntity(kind="polyline", layer=layer, points=points)
        if closed and len(points) >= 3:
            polyline = (points, layer)
            if any(token in layer.lower() for token in SHAFT_LAYER_TOKENS):
                box = bbox(points)
                shaft = Shaft(
                    id=f"S-{round(box.center.x)}-{round(box.center.y)}",
                    position=box.center,
                    width_mm=box.width,
                    depth_mm=box.height,
                )
    elif kind == "LINE":
        start = _point(entity.dxf.start.x, entity.dxf.start.y, scale)
        end = _point(entity.dxf.end.x, entity.dxf.end.y, scale)
        item = DrawingEntity(kind="line", layer=layer, points=[start, end])
        if any(token in layer.lower() for token in DOOR_LAYER_TOKENS):
            midpoint = Point(x=(start.x + end.x) / 2, y=(start.y + end.y) / 2)
            door = Door(
                id=f"D-{round(midpoint.x)}-{round(midpoint.y)}",
                position=midpoint,
                width_mm=distance(start, end) or 900.0,
            )
    elif kind == "CIRCLE":
        center = _point(entity.dxf.center.x, entity.dxf.center.y, scale)
        radius = float(entity.dxf.radius) * scale.mm_per_unit
        item = DrawingEntity(kind="circle", layer=layer, center=center, radius=radius)
    elif kind == "ARC":
        center = _point(entity.dxf.center.x, entity.dxf.center.y, scale)
        radius = float(entity.dxf.radius) * scale.mm_per_unit
        item = DrawingEntity(kind="arc", layer=layer, center=center, radius=radius)
    elif kind in ("TEXT", "MTEXT"):
        raw_text = entity.plain_text() if kind == "MTEXT" else str(entity.dxf.text)
        position = _point(entity.dxf.insert.x, entity.dxf.insert.y, scale)
        item = DrawingEntity(kind="text", layer=layer, position=position, text=raw_text)
        if raw_text.strip():
            text = (raw_text.strip(), position)
        if "shaft" in raw_text.lower():
            shaft = Shaft(id=f"S-{round(position.x)}-{round(position.y)}", position=position)
    elif kind == "INSERT":
        position = _point(entity.dxf.insert.x, entity.dxf.insert.y, scale)
        name = str(entity.dxf.name)
        item = DrawingEntity(kind="insert", layer=layer, position=position, block_name=name)
        if any(token in name.lower() for token in DOOR_LAYER_TOKENS) or any(
            token in layer.lower() for token in DOOR_LAYER_TOKENS
        ):
            door = Door(
                id=f"D-{round(position.x)}-{round(position.y)}",
                position=position,
                width_mm=_width_from_name(name),
            )
    return item, polyline, text, door, shaft


def _detect_rooms(
    closed_polylines: list[tuple[list[Point], str]], texts: list[tuple[str, Point]]
) -> list[Room]:
    candidates: list[tuple[list[Point], str, float]] = []
    for points, layer in closed_polylines:
        area_m2 = polygon_area(points) / 1_000_000.0
        if not 0.8 <= area_m2 <= 100.0:
            continue
        candidates.append((points, layer, area_m2))
    if not candidates:
        return []

    preferred = [
        candidate
        for candidate in candidates
        if any(token in candidate[1].lower() for token in ROOM_LAYER_TOKENS)
    ]
    pool = preferred or candidates

    rooms: list[Room] = []
    for index, (points, _layer, _area) in enumerate(pool, start=1):
        box = bbox(points)
        name = _nearest_text_name(points, texts, box.center)
        rooms.append(
            Room(
                id=f"R-{index:02d}",
                name=name,
                boundary=points,
                closed=True,
            )
        )
    return rooms


def _nearest_text_name(
    points: list[Point], texts: list[tuple[str, Point]], centroid: Point
) -> str | None:
    best: tuple[float, str] | None = None
    for text, position in texts:
        if not point_in_polygon(position, points):
            continue
        score = distance(position, centroid)
        if best is None or score < best[0]:
            best = (score, text)
    return best[1] if best is not None else None


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
