from __future__ import annotations

import math
from html import escape

from core.geometry import BBox, Point, bbox
from core.layers import LayerRole, classify_layer
from core.models import (
    Building,
    Design,
    DetectedFixture,
    DrawingEntity,
    Fixture,
    Pipe,
    PlumbingItem,
    PlumbingItemType,
    Room,
    Shaft,
    ShaftService,
)

DEFAULT_TEXT_MM = 140.0
PIPE_TEXT_MM = 110.0
PLAN_ROLES = {
    LayerRole.WALL.value,
    LayerRole.DOOR.value,
    LayerRole.WINDOW.value,
    LayerRole.ROOM.value,
    LayerRole.SHAFT.value,
}


def render_svg(building: Building, design: Design | None = None, width: int = 1200) -> str:
    extent = _extent(building, design)
    pad = max(150.0, max(extent.width, extent.height) * 0.05)
    view = BBox(
        minx=extent.minx - pad,
        miny=extent.miny - pad,
        maxx=extent.maxx + pad,
        maxy=extent.maxy + pad,
    )

    def sy(y: float) -> float:
        return view.miny + (view.maxy - y)

    def points_attr(points: list[Point]) -> str:
        return " ".join(f"{p.x:.3f},{sy(p.y):.3f}" for p in points)

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view.minx:.3f} {view.miny:.3f} '
        f'{view.width:.3f} {view.height:.3f}" width="100%" style="max-width:{width}px" '
        'role="img" aria-label="Bathroom plumbing plan">',
        _style(),
    ]

    parts.append('<g class="background">')
    for entity in building.entities:
        rendered = _render_entity(entity, sy, points_attr)
        if rendered:
            parts.append(rendered)
    parts.append("</g>")

    parts.append('<g class="rooms">')
    for room in building.rooms:
        parts.append(_render_room(room, sy, points_attr))
    parts.append("</g>")

    parts.append('<g class="detected-fixtures">')
    for fixture in building.detected_fixtures:
        parts.append(_render_detected_fixture(fixture, sy))
    parts.append("</g>")

    parts.append('<g class="openings">')
    for shaft in building.shafts:
        parts.append(_render_shaft(shaft, sy))
    parts.append("</g>")

    if design is not None:
        parts.append('<g class="design">')
        for pipe in design.pipes:
            parts.append(_render_pipe(pipe, sy, points_attr))
        for pipe in design.vent_pipes:
            parts.append(_render_pipe(pipe, sy, points_attr))
        for pipe in design.supply_pipes:
            parts.append(_render_pipe(pipe, sy, points_attr))
        for fixture in design.fixtures:
            parts.append(_render_fixture(fixture, sy))
        for vent_stack in _vent_stacks(design):
            parts.append(
                f'<circle class="vent-stack" cx="{vent_stack.position.x:.3f}" '
                f'cy="{sy(vent_stack.position.y):.3f}" '
                f'r="{max(vent_stack.diameter_mm / 2, 100):.3f}">'
                f'<title>Vent stack {escape(vent_stack.id)}</title></circle>'
            )
        if design.water_source is not None:
            parts.append(
                f'<rect class="water-source" x="{design.water_source.position.x - 250:.3f}" '
                f'y="{sy(design.water_source.position.y) - 250:.3f}" width="500" height="500" rx="60">'
                f'<title>Water source {escape(design.water_source.id)}</title></rect>'
            )
        for item in design.plumbing_items:
            parts.append(_render_plumbing_item(item, sy))
        for stack in _soil_stacks(design):
            parts.append(
                f'<circle class="stack" cx="{stack.position.x:.3f}" '
                f'cy="{sy(stack.position.y):.3f}" r="{max(stack.diameter_mm / 2, 120):.3f}">'
                f'<title>Stack {escape(stack.id)}</title></circle>'
            )
        parts.append("</g>")

    parts.append("</svg>")
    return "".join(parts)


def _soil_stacks(design: Design) -> list:
    stacks = list(design.stacks) or [design.stack]
    if design.stack.id not in {stack.id for stack in stacks}:
        stacks.insert(0, design.stack)
    return stacks


def _vent_stacks(design: Design) -> list:
    vent_stacks = list(design.vent_stacks)
    if design.vent_stack is not None and design.vent_stack.id not in {
        stack.id for stack in vent_stacks
    }:
        vent_stacks.insert(0, design.vent_stack)
    return vent_stacks


def _extent(building: Building, design: Design | None) -> BBox:
    plan_points = _entity_points(building.entities, plan_only=True)
    points = plan_points or _entity_points(building.entities, plan_only=False)
    for room in building.rooms:
        points.extend(room.boundary)
    for door in building.doors:
        points.append(door.position)
    for shaft in building.shafts:
        points.extend(_shaft_corners(shaft))
    for fixture in building.detected_fixtures:
        points.extend(
            [
                Point(x=fixture.position.x - fixture.width_mm / 2, y=fixture.position.y - fixture.depth_mm / 2),
                Point(x=fixture.position.x + fixture.width_mm / 2, y=fixture.position.y + fixture.depth_mm / 2),
            ]
        )
    if design is not None:
        for fixture in design.fixtures:
            points.extend(_fixture_corners(fixture))
        for pipe in [*design.pipes, *design.vent_pipes]:
            points.extend(pipe.points)
        for pipe in design.supply_pipes:
            points.extend(pipe.points)
        for item in design.plumbing_items:
            points.append(item.position)
        points.extend(stack.position for stack in _soil_stacks(design))
        points.extend(stack.position for stack in _vent_stacks(design))
        if design.water_source is not None:
            points.append(design.water_source.position)
    return bbox(points) if points else BBox(0.0, 0.0, 1000.0, 1000.0)


def _entity_points(entities: list[DrawingEntity], *, plan_only: bool) -> list[Point]:
    points: list[Point] = []
    for entity in entities:
        role = _role(entity)
        if plan_only and role not in PLAN_ROLES:
            continue
        if role == LayerRole.ANNOTATION.value or entity.kind == "text":
            continue
        points.extend(entity.points)
        if entity.center:
            points.append(entity.center)
            if entity.radius:
                points.extend(
                    [
                        Point(x=entity.center.x - entity.radius, y=entity.center.y - entity.radius),
                        Point(x=entity.center.x + entity.radius, y=entity.center.y + entity.radius),
                    ]
                )
        if entity.position:
            points.append(entity.position)
    return points


def _role(entity: DrawingEntity) -> str:
    if entity.role and entity.role != LayerRole.OTHER.value:
        return entity.role
    return classify_layer(entity.layer).value


def _render_entity(entity: DrawingEntity, sy, points_attr) -> str:
    role = _role(entity)
    if role == LayerRole.ANNOTATION.value or entity.kind == "text":
        return ""
    layer_class = _layer_class(entity.layer)
    if entity.kind == "line" and len(entity.points) >= 2:
        start, end = entity.points[0], entity.points[1]
        return (
            f'<line class="bg {layer_class}" x1="{start.x:.3f}" y1="{sy(start.y):.3f}" '
            f'x2="{end.x:.3f}" y2="{sy(end.y):.3f}"/>'
        )
    if entity.kind == "polyline" and entity.points:
        if (
            entity.closed
            and role == LayerRole.WALL.value
            and _is_wall_band(entity.points)
        ):
            return f'<polygon class="bg wall-fill" points="{points_attr(entity.points)}"/>'
        return f'<polyline class="bg {layer_class}" points="{points_attr(entity.points)}"/>'
    if entity.kind == "arc" and entity.center and entity.radius:
        arc_points = entity.points or _arc_points(
            entity.center,
            entity.radius,
            entity.start_angle,
            entity.end_angle,
        )
        if arc_points:
            return (
                f'<polyline class="bg {layer_class}" '
                f'points="{points_attr(arc_points)}"/>'
            )
    if entity.kind == "circle" and entity.center and entity.radius:
        return (
            f'<circle class="bg {layer_class}" cx="{entity.center.x:.3f}" '
            f'cy="{sy(entity.center.y):.3f}" r="{entity.radius:.3f}"/>'
        )
    if entity.kind == "insert" and entity.position:
        return (
            f'<circle class="bg-block" cx="{entity.position.x:.3f}" '
            f'cy="{sy(entity.position.y):.3f}" r="80"/>'
        )
    return ""


def _render_detected_fixture(fixture: DetectedFixture, sy) -> str:
    half_width = fixture.width_mm / 2
    half_depth = fixture.depth_mm / 2
    label = _detected_fixture_label(fixture.type)
    return (
        f'<g class="detected-fixture detected-fixture-{fixture.type.value}" '
        f'data-fixture-id="{escape(fixture.id)}">'
        f'<rect x="{fixture.position.x - half_width:.3f}" '
        f'y="{sy(fixture.position.y + half_depth):.3f}" '
        f'width="{fixture.width_mm:.3f}" height="{fixture.depth_mm:.3f}" rx="60">'
        f'<title>{escape(fixture.id)} · {escape(label)} · '
        f'{fixture.width_mm:.0f}×{fixture.depth_mm:.0f} mm</title></rect>'
        f'<text class="detected-fixture-label" x="{fixture.position.x:.3f}" '
        f'y="{sy(fixture.position.y):.3f}" font-size="{PIPE_TEXT_MM:.1f}" '
        f'text-anchor="middle">{escape(label)}</text>'
        f'</g>'
    )


def _detected_fixture_label(fixture_type) -> str:
    return {
        "WC": "WC",
        "BASIN": "BASIN",
        "SHOWER": "SHOWER",
        "FLOOR_DRAIN": "FD",
        "KITCHEN_SINK": "SINK",
    }.get(fixture_type.value, fixture_type.value)


def _render_room(room: Room, sy, points_attr) -> str:
    centroid = room.bbox.center
    name = room.name or f"Room {room.id}"
    label = f"{name} · {room.area_m2:.2f} m2"
    size = _room_label_size(room)
    return (
        f'<polygon class="room" data-room-id="{escape(room.id)}" '
        f'points="{points_attr(room.boundary)}"><title>{escape(room.id)}</title></polygon>'
        f'<text class="room-label" x="{centroid.x:.3f}" y="{sy(centroid.y):.3f}" '
        f'font-size="{size:.1f}" text-anchor="middle">{escape(label)}</text>'
    )


def _render_shaft(shaft: Shaft, sy) -> str:
    box = shaft.bbox
    parts = [
        f'<g class="shaft-group" data-shaft-id="{escape(shaft.id)}">',
        f'<rect class="shaft" x="{box.minx:.3f}" y="{sy(box.maxy):.3f}" '
        f'width="{box.width:.3f}" height="{box.height:.3f}">'
        f'<title>{escape(shaft.name or shaft.id)} · '
        f'{", ".join(service.value for service in shaft.services)}</title></rect>',
    ]
    radius = max(45.0, min(box.width, box.height) * 0.12)
    offsets = {
        ShaftService.DRAIN: 0.0,
        ShaftService.WATER: -0.24,
        ShaftService.VENT: 0.24,
    }
    for service in shaft.services:
        offset = offsets[service] * box.width
        x = shaft.position.x + offset
        y = sy(shaft.position.y)
        label = {"DRAIN": "D", "WATER": "W", "VENT": "V"}[service.value]
        parts.append(
            f'<circle class="shaft-service shaft-service-{service.value.lower()}" '
            f'cx="{x:.3f}" cy="{y:.3f}" r="{radius:.3f}">'
            f'<title>{escape(service.value)} service</title></circle>'
            f'<text class="shaft-service-label" x="{x:.3f}" '
            f'y="{y + radius * 0.35:.3f}" font-size="{max(60.0, radius * 0.9):.1f}" '
            f'text-anchor="middle">{label}</text>'
        )
    parts.append("</g>")
    return "".join(parts)


def _render_fixture(fixture: Fixture, sy) -> str:
    if fixture.source == "existing":
        return (
            f'<text class="fixture-tag fixture-label" x="{fixture.position.x:.3f}" '
            f'y="{sy(fixture.position.y):.3f}" font-size="{PIPE_TEXT_MM:.1f}" '
            f'text-anchor="middle"><title>{escape(fixture.id)}</title>'
            f'{escape(fixture.type.value)}</text>'
        )
    box = fixture.bbox
    return (
        f'<rect class="fixture fixture-{fixture.type.value}" x="{box.minx:.3f}" '
        f'y="{sy(box.maxy):.3f}" width="{box.width:.3f}" height="{box.height:.3f}" rx="60">'
        f'<title>{escape(fixture.id)}</title></rect>'
        f'<text class="fixture-label" x="{fixture.position.x:.3f}" '
        f'y="{sy(fixture.position.y):.3f}" font-size="{PIPE_TEXT_MM:.1f}" text-anchor="middle">'
        f'{escape(fixture.type.value)}</text>'
    )


def _render_pipe(pipe: Pipe, sy, points_attr) -> str:
    label_point = _polyline_midpoint(pipe.points)
    return (
        f'<polyline class="pipe pipe-{pipe.system.value}" points="{points_attr(pipe.points)}">'
        f'<title>{escape(pipe.id)}</title></polyline>'
        f'<text class="pipe-label" x="{label_point.x:.3f}" y="{sy(label_point.y) - 90:.3f}" '
        f'font-size="{PIPE_TEXT_MM:.1f}" text-anchor="middle">{pipe.diameter_mm:g}mm</text>'
    )


def _render_plumbing_item(item: PlumbingItem, sy) -> str:
    x = item.position.x
    y = sy(item.position.y)
    size = 130.0
    if item.type in (
        PlumbingItemType.WATER_HEATER,
        PlumbingItemType.EXPANSION_TANK,
    ):
        size = 230.0
    elif item.type == PlumbingItemType.FIXTURE_STOP:
        size = 70.0
    elif item.type in (PlumbingItemType.MAIN_SHUTOFF, PlumbingItemType.CHECK_VALVE):
        size = 110.0
    return (
        f'<rect class="plumbing-item item-{item.type.value.lower()}" '
        f'x="{x - size / 2:.3f}" y="{y - size / 2:.3f}" '
        f'width="{size:.3f}" height="{size:.3f}" rx="{size * 0.2:.3f}">'
        f'<title>{escape(item.tag or item.type.value)}</title></rect>'
    )


def _polyline_midpoint(points: list[Point]) -> Point:
    if not points:
        return Point(x=0, y=0)
    return points[len(points) // 2]


def _shaft_corners(shaft: Shaft) -> list[Point]:
    box = shaft.bbox
    return [
        Point(x=box.minx, y=box.miny),
        Point(x=box.maxx, y=box.maxy),
    ]


def _fixture_corners(fixture: Fixture) -> list[Point]:
    box = fixture.bbox
    return [
        Point(x=box.minx, y=box.miny),
        Point(x=box.maxx, y=box.maxy),
    ]


def _is_wall_band(points: list[Point]) -> bool:
    if len(points) < 4:
        return False
    box = bbox(points)
    short = min(box.width, box.height)
    long = max(box.width, box.height)
    return short > 0 and long >= 200 and long / short >= 2.0


def _arc_points(
    center: Point,
    radius: float,
    start_angle: float | None,
    end_angle: float | None,
) -> list[Point]:
    if start_angle is None or end_angle is None:
        return []
    delta = (float(end_angle) - float(start_angle)) % 360.0
    if delta < 0.01:
        delta = 360.0
    steps = max(8, min(96, int(delta / 7.5) + 1))
    points: list[Point] = []
    for index in range(steps + 1):
        angle = math.radians(float(start_angle) + delta * index / steps)
        points.append(
            Point(
                x=center.x + radius * math.cos(angle),
                y=center.y + radius * math.sin(angle),
            )
        )
    return points


def _room_label_size(room: Room) -> float:
    box = room.bbox
    if box.width <= 0 or box.height <= 0:
        return DEFAULT_TEXT_MM
    return max(80.0, min(DEFAULT_TEXT_MM, box.width * 0.08, box.height * 0.12))


def _layer_class(layer: str) -> str:
    lowered = layer.lower()
    if "wall" in lowered:
        return "wall"
    if "room" in lowered:
        return "room-outline"
    if "door" in lowered:
        return "door-line"
    if "window" in lowered or "glaz" in lowered:
        return "window-line"
    if "shaft" in lowered or "duct" in lowered:
        return "shaft-line"
    return "misc"


def _style() -> str:
    return """<style>
  .bg { }
  .wall { stroke: #1f2937; fill: none; stroke-width: 30; stroke-linecap: round; }
  .wall-fill { fill: #1f2937; stroke: #1f2937; stroke-width: 8; }
  .room-outline { stroke: #cbd5e1; fill: none; stroke-width: 18; }
  .misc { stroke: #cbd5e1; fill: none; stroke-width: 12; }
  .window-line { stroke: #0284c7; fill: none; stroke-width: 22; }
  .door-line { stroke: #b45309; fill: none; stroke-width: 22; }
  .shaft-line { stroke: #4f46e5; fill: none; stroke-width: 20; stroke-dasharray: 60 40; }
  .bg-label { fill: #94a3b8; font-family: ui-sans-serif, system-ui, sans-serif; }
  .bg-block { fill: #e5e7eb; stroke: #9ca3af; stroke-width: 12; }
  .room { fill: #f8fafc; fill-opacity: 0.62; stroke: #cbd5e1; stroke-width: 18; }
  .room-label { fill: #475569; font-family: ui-sans-serif, system-ui, sans-serif; pointer-events: none; }
  .shaft { fill: #eef2ff; stroke: #4f46e5; stroke-width: 18; stroke-dasharray: 60 40; }
  .shaft-service { stroke-width: 14; }
  .shaft-service-drain { fill: #fee2e2; stroke: #dc2626; }
  .shaft-service-water { fill: #dbeafe; stroke: #2563eb; }
  .shaft-service-vent { fill: #dcfce7; stroke: #16a34a; }
  .shaft-service-label { fill: #1e293b; font-family: ui-sans-serif, system-ui, sans-serif; font-weight: 700; pointer-events: none; }
  .detected-fixture rect { fill: #dbeafe; fill-opacity: 0.24; stroke: #2563eb; stroke-width: 24; stroke-dasharray: 50 30; }
  .detected-fixture-BASIN rect { fill: #e0f2fe; stroke: #0284c7; }
  .detected-fixture-SHOWER rect { fill: #eff6ff; stroke: #1d4ed8; }
  .detected-fixture-FLOOR_DRAIN rect { fill: #fef3c7; stroke: #b45309; }
  .detected-fixture-KITCHEN_SINK rect { fill: #f0fdf4; stroke: #15803d; }
  .detected-fixture-label { fill: #1d4ed8; font-family: ui-sans-serif, system-ui, sans-serif; font-weight: 700; pointer-events: none; }
  .fixture { fill: #dbeafe; stroke: #2563eb; stroke-width: 22; }
  .fixture-WC { fill: #e0f2fe; }
  .fixture-SHOWER { fill: #eff6ff; }
  .fixture-label { fill: #1d4ed8; font-family: ui-sans-serif, system-ui, sans-serif; font-weight: 600; }
  .pipe { fill: none; stroke-width: 55; stroke-linecap: round; stroke-linejoin: round; }
  .pipe-SOIL { stroke: #dc2626; }
  .pipe-WASTE { stroke: #d97706; }
  .pipe-VENT { stroke: #16a34a; stroke-dasharray: 140 80; }
  .pipe-COLD_WATER { stroke: #2563eb; stroke-width: 40; }
  .pipe-HOT_WATER { stroke: #ea580c; stroke-width: 40; }
  .pipe-label { fill: #7f1d1d; font-family: ui-sans-serif, system-ui, sans-serif; font-weight: 600; }
  .stack { fill: #fee2e2; stroke: #dc2626; stroke-width: 24; }
  .vent-stack { fill: #ecfdf5; stroke: #16a34a; stroke-width: 18; stroke-dasharray: 60 40; }
  .water-source { fill: #eff6ff; stroke: #2563eb; stroke-width: 18; }
  .plumbing-item { fill: #f5f3ff; stroke: #7c3aed; stroke-width: 16; }
  .item-water_heater, .item-expansion_tank { fill: #fff7ed; stroke: #ea580c; }
  .item-cleanout { fill: #f8fafc; stroke: #475569; }
</style>"""
