from __future__ import annotations

import math
from dataclasses import dataclass

from shapely.geometry import LineString, Polygon
from shapely.geometry import Point as ShapelyPoint
from shapely.ops import polygonize, unary_union

from core.geometry import Point, bbox, distance
from core.models import DrawingEntity, Room

MIN_ROOM_AREA_M2 = 0.5
MIN_INFERRED_ROOM_AREA_M2 = 1.0
MAX_ROOM_AREA_M2 = 300.0
MIN_WALL_GAP_MM = 25.0
MAX_BRIDGED_GAP_MM = 1500.0
LINE_GROUP_TOLERANCE_MM = 5.0


@dataclass(frozen=True)
class RoomLabel:
    text: str
    point: Point
    layer: str
    score: int


@dataclass
class RoomDetectionResult:
    rooms: list[Room]
    warnings: list[str]


def detect_rooms(entities: list[DrawingEntity]) -> RoomDetectionResult:
    labels = _collect_labels(entities)
    explicit = _explicit_room_polygons(entities)
    explicit_rooms = _labeled_rooms(explicit, labels, preserve_order=True)
    if explicit_rooms:
        return RoomDetectionResult(rooms=explicit_rooms, warnings=[])

    wall_segments = _wall_segments(entities)
    window_segments = _window_segments(entities)
    if not wall_segments:
        if explicit:
            return RoomDetectionResult(
                rooms=_named_rooms(explicit),
                warnings=[],
            )
        return RoomDetectionResult(
            rooms=[],
            warnings=[
                "No closed room boundaries found and no wall lines were detected. "
                "Draw room polylines or wall lines to enable room detection."
            ],
        )

    network = _closed_wall_network(wall_segments, window_segments)
    faces = _faces(network)
    inferred = _labeled_rooms(faces, labels, preserve_order=False)
    if inferred:
        warnings = []
        if len(inferred) < len(labels):
            warnings.append(
                f"{len(labels) - len(inferred)} room label(s) could not be matched "
                "to an enclosed space."
            )
        warnings.append(
            "Room boundaries were inferred from wall geometry; verify openings and areas."
        )
        return RoomDetectionResult(rooms=inferred, warnings=warnings)

    if explicit:
        return RoomDetectionResult(rooms=_named_rooms(explicit), warnings=[])

    return RoomDetectionResult(
        rooms=[],
        warnings=[
            "No closed room boundaries found. Draw closed room polylines or wall lines "
            "with labels inside each room."
        ],
    )


def _collect_labels(entities: list[DrawingEntity]) -> list[RoomLabel]:
    labels: list[RoomLabel] = []
    for entity in entities:
        if entity.role != "room_label" or not entity.text or not entity.position:
            continue
        text = " ".join(entity.text.split())
        if not text:
            continue
        score = 30 if "room" in entity.layer.lower() else 10
        labels.append(
            RoomLabel(text=text, point=entity.position, layer=entity.layer, score=score)
        )
    return labels


def _explicit_room_polygons(entities: list[DrawingEntity]) -> list[Polygon]:
    polygons: list[Polygon] = []
    for entity in entities:
        if entity.role != "room" or entity.kind != "polyline" or not entity.closed:
            continue
        if len(entity.points) < 3:
            continue
        polygon = _polygon(entity.points)
        if polygon is None:
            continue
        area_m2 = polygon.area / 1_000_000.0
        if MIN_ROOM_AREA_M2 <= area_m2 <= MAX_ROOM_AREA_M2:
            polygons.append(polygon)
    return polygons


def _labeled_rooms(
    polygons: list[Polygon], labels: list[RoomLabel], *, preserve_order: bool
) -> list[Room]:
    matched: list[tuple[Polygon, RoomLabel | None]] = []
    for polygon in polygons:
        matched.append((polygon, _label_for_polygon(polygon, labels)))
    if not preserve_order:
        matched.sort(
            key=lambda item: (
                -item[0].centroid.y,
                item[0].centroid.x,
            )
        )
    return [
        _room_from_polygon(polygon, label.text if label else None, index)
        for index, (polygon, label) in enumerate(matched, start=1)
    ]


def _named_rooms(polygons: list[Polygon]) -> list[Room]:
    return [
        _room_from_polygon(polygon, None, index)
        for index, polygon in enumerate(polygons, start=1)
    ]


def _room_from_polygon(polygon: Polygon, name: str | None, index: int) -> Room:
    coords = list(polygon.exterior.coords)
    if len(coords) > 1 and coords[0] == coords[-1]:
        coords = coords[:-1]
    return Room(
        id=f"R-{index:02d}",
        name=name,
        boundary=[Point(x=float(x), y=float(y)) for x, y in coords],
        closed=True,
    )


def _label_for_polygon(polygon: Polygon, labels: list[RoomLabel]) -> RoomLabel | None:
    search_area = polygon.buffer(25.0)
    candidates = [
        label
        for label in labels
        if search_area.contains(ShapelyPoint(label.point.x, label.point.y))
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda label: (
            label.score,
            -distance(label.point, Point(x=polygon.centroid.x, y=polygon.centroid.y)),
        ),
    )


def _wall_segments(entities: list[DrawingEntity]) -> list[tuple[Point, Point]]:
    segments: list[tuple[Point, Point]] = []
    for entity in entities:
        if entity.role != "wall":
            continue
        if entity.kind == "line":
            if len(entity.points) >= 2:
                segments.append((entity.points[0], entity.points[1]))
            continue
        if entity.kind != "polyline" or len(entity.points) < 2:
            continue
        points = entity.points
        if entity.closed and len(points) >= 4:
            box = bbox(points)
            short = min(box.width, box.height)
            long = max(box.width, box.height)
            if (
                short > 0
                and long >= 200
                and long / short >= 2.0
            ):
                if box.width >= box.height:
                    center_y = (box.miny + box.maxy) / 2.0
                    segments.append(
                        (
                            Point(x=box.minx, y=center_y),
                            Point(x=box.maxx, y=center_y),
                        )
                    )
                else:
                    center_x = (box.minx + box.maxx) / 2.0
                    segments.append(
                        (
                            Point(x=center_x, y=box.miny),
                            Point(x=center_x, y=box.maxy),
                        )
                    )
                continue
        for index, start in enumerate(points):
            end = points[(index + 1) % len(points)]
            if distance(start, end) >= MIN_WALL_GAP_MM:
                segments.append((start, end))
            if not entity.closed and index == len(points) - 2:
                break
    return segments


def _window_segments(entities: list[DrawingEntity]) -> list[tuple[Point, Point]]:
    segments: list[tuple[Point, Point]] = []
    for entity in entities:
        if entity.role != "window":
            continue
        if entity.kind == "line" and len(entity.points) >= 2:
            segments.append((entity.points[0], entity.points[1]))
            continue
        if entity.kind == "polyline":
            points = entity.points
            for index, start in enumerate(points):
                end = points[(index + 1) % len(points)]
                if distance(start, end) >= MIN_WALL_GAP_MM:
                    segments.append((start, end))
                if not entity.closed and index == len(points) - 2:
                    break
    return segments


def _closed_wall_network(
    wall_segments: list[tuple[Point, Point]],
    window_segments: list[tuple[Point, Point]],
) -> list[LineString]:
    groups: dict[tuple[float, float], list[tuple[Point, Point, float, float, float]]] = {}
    for start, end in wall_segments:
        dx = end.x - start.x
        dy = end.y - start.y
        length = math.hypot(dx, dy)
        if length < MIN_WALL_GAP_MM:
            continue
        ux, uy = dx / length, dy / length
        if ux < -1e-9 or (abs(ux) < 1e-9 and uy < 0):
            ux, uy = -ux, -uy
        angle = math.atan2(uy, ux)
        offset = ux * start.y - uy * start.x
        key = (
            round(angle / (LINE_GROUP_TOLERANCE_MM / 1000.0)),
            round(offset / LINE_GROUP_TOLERANCE_MM),
        )
        groups.setdefault(key, []).append((start, end, ux, uy, offset))

    lines: list[LineString] = [
        LineString([(start.x, start.y), (end.x, end.y)])
        for start, end in wall_segments + window_segments
    ]
    lines.extend(_junction_connectors(wall_segments))

    for items in groups.values():
        ux, uy = items[0][2], items[0][3]
        offset = items[0][4]
        intervals: list[tuple[float, float]] = []
        for start, end, _, _, _ in items:
            t_start = start.x * ux + start.y * uy
            t_end = end.x * ux + end.y * uy
            intervals.append((min(t_start, t_end), max(t_start, t_end)))
        intervals.sort()
        merged: list[tuple[float, float]] = []
        for start, end in intervals:
            if merged and start <= merged[-1][1] + 1.0:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        for current, following in zip(merged, merged[1:], strict=False):
            gap = following[0] - current[1]
            if 1.0 < gap <= MAX_BRIDGED_GAP_MM:
                start = _point_on_line(ux, uy, offset, current[1])
                end = _point_on_line(ux, uy, offset, following[0])
                lines.append(LineString([(start.x, start.y), (end.x, end.y)]))

    return lines


def _junction_connectors(segments: list[tuple[Point, Point]]) -> list[LineString]:
    lines = [
        LineString([(start.x, start.y), (end.x, end.y)]) for start, end in segments
    ]
    connectors: list[LineString] = []
    seen: set[tuple[float, float, float, float]] = set()
    for index, (start, end) in enumerate(segments):
        direction = _unit(start, end)
        if direction is None:
            continue
        for endpoint in (start, end):
            best: tuple[float, ShapelyPoint] | None = None
            target = ShapelyPoint(endpoint.x, endpoint.y)
            for other_index, other in enumerate(lines):
                if other_index == index or other.length < MIN_WALL_GAP_MM:
                    continue
                other_direction = _unit(
                    Point(x=other.coords[0][0], y=other.coords[0][1]),
                    Point(x=other.coords[-1][0], y=other.coords[-1][1]),
                )
                if other_direction is None:
                    continue
                if abs(direction[0] * other_direction[0] + direction[1] * other_direction[1]) > 0.9:
                    continue
                projected = other.interpolate(other.project(target))
                gap = distance(endpoint, Point(x=projected.x, y=projected.y))
                if 1.0 < gap <= 300.0 and (best is None or gap < best[0]):
                    best = (gap, projected)
            if best is None:
                continue
            projected = best[1]
            key = (
                round(endpoint.x, 1),
                round(endpoint.y, 1),
                round(projected.x, 1),
                round(projected.y, 1),
            )
            if key in seen:
                continue
            seen.add(key)
            connectors.append(
                LineString(
                    [(endpoint.x, endpoint.y), (projected.x, projected.y)]
                )
            )
    return connectors


def _unit(start: Point, end: Point) -> tuple[float, float] | None:
    dx = end.x - start.x
    dy = end.y - start.y
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return None
    return dx / length, dy / length


def _point_on_line(ux: float, uy: float, offset: float, t: float) -> Point:
    nx, ny = -uy, ux
    return Point(
        x=ux * t + offset * nx,
        y=uy * t + offset * ny,
    )


def _faces(lines: list[LineString]) -> list[Polygon]:
    if not lines:
        return []
    network = unary_union(lines)
    polygons = []
    for polygon in polygonize(network):
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        if polygon.is_empty:
            continue
        if polygon.geom_type == "MultiPolygon":
            polygon = max(polygon.geoms, key=lambda item: item.area)
        if polygon.geom_type != "Polygon":
            continue
        area_m2 = polygon.area / 1_000_000.0
        if MIN_INFERRED_ROOM_AREA_M2 <= area_m2 <= MAX_ROOM_AREA_M2:
            polygons.append(polygon)
    return polygons


def _polygon(points: list[Point]) -> Polygon | None:
    if len(points) < 3:
        return None
    try:
        polygon = Polygon([(point.x, point.y) for point in points])
    except ValueError:
        return None
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    if polygon.is_empty:
        return None
    if polygon.geom_type == "MultiPolygon":
        polygon = max(polygon.geoms, key=lambda item: item.area)
    if polygon.geom_type != "Polygon":
        return None
    return polygon


def _dedupe_rooms(rooms: list[Room]) -> list[Room]:
    result: list[Room] = []
    for room in rooms:
        duplicate = next(
            (
                existing
                for existing in result
                if (existing.name or "").lower() == (room.name or "").lower()
                and existing.area_m2 > 0
            ),
            None,
        )
        if duplicate is not None:
            if room.area_m2 > duplicate.area_m2:
                result[result.index(duplicate)] = room
            continue
        result.append(room)
    for index, room in enumerate(result, start=1):
        room.id = f"R-{index:02d}"
    return result
