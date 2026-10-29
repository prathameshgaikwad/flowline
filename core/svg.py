from __future__ import annotations

from html import escape

from core.geometry import BBox, Point, bbox
from core.models import Building, Design, DrawingEntity, Fixture, Pipe, Room, Shaft

DEFAULT_TEXT_MM = 140.0
PIPE_TEXT_MM = 110.0


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
        parts.append(_render_entity(entity, sy, points_attr))
    parts.append("</g>")

    parts.append('<g class="rooms">')
    for room in building.rooms:
        parts.append(_render_room(room, sy, points_attr))
    parts.append("</g>")

    parts.append('<g class="openings">')
    for door in building.doors:
        parts.append(
            f'<circle class="door" cx="{door.position.x:.3f}" cy="{sy(door.position.y):.3f}" '
            f'r="{max(door.width_mm / 2, 150):.3f}"><title>{escape(door.id)}</title></circle>'
        )
    for shaft in building.shafts:
        parts.append(_render_shaft(shaft, sy))
    parts.append("</g>")

    if design is not None:
        parts.append('<g class="design">')
        for pipe in design.pipes:
            parts.append(_render_pipe(pipe, sy, points_attr))
        for fixture in design.fixtures:
            parts.append(_render_fixture(fixture, sy))
        parts.append(
            f'<circle class="stack" cx="{design.stack.position.x:.3f}" '
            f'cy="{sy(design.stack.position.y):.3f}" r="{max(design.stack.diameter_mm / 2, 120):.3f}">'
            f'<title>Stack {escape(design.stack.id)}</title></circle>'
        )
        parts.append("</g>")

    parts.append("</svg>")
    return "".join(parts)


def _extent(building: Building, design: Design | None) -> BBox:
    points: list[Point] = []
    for entity in building.entities:
        points.extend(entity.points)
        if entity.center:
            points.append(entity.center)
        if entity.position:
            points.append(entity.position)
    for room in building.rooms:
        points.extend(room.boundary)
    for door in building.doors:
        points.append(door.position)
    for shaft in building.shafts:
        points.extend(_shaft_corners(shaft))
    if design is not None:
        for fixture in design.fixtures:
            points.extend(_fixture_corners(fixture))
        for pipe in design.pipes:
            points.extend(pipe.points)
        points.append(design.stack.position)
    return bbox(points) if points else BBox(0.0, 0.0, 1000.0, 1000.0)


def _render_entity(entity: DrawingEntity, sy, points_attr) -> str:
    layer_class = _layer_class(entity.layer)
    if entity.kind == "line" and len(entity.points) >= 2:
        start, end = entity.points[0], entity.points[1]
        return (
            f'<line class="bg {layer_class}" x1="{start.x:.3f}" y1="{sy(start.y):.3f}" '
            f'x2="{end.x:.3f}" y2="{sy(end.y):.3f}"/>'
        )
    if entity.kind == "polyline" and entity.points:
        return f'<polyline class="bg {layer_class}" points="{points_attr(entity.points)}"/>'
    if entity.kind in ("circle", "arc") and entity.center and entity.radius:
        return (
            f'<circle class="bg {layer_class}" cx="{entity.center.x:.3f}" '
            f'cy="{sy(entity.center.y):.3f}" r="{entity.radius:.3f}"/>'
        )
    if entity.kind == "text" and entity.position and entity.text:
        return (
            f'<text class="bg-label {layer_class}" x="{entity.position.x:.3f}" '
            f'y="{sy(entity.position.y):.3f}" font-size="{DEFAULT_TEXT_MM:.1f}" '
            f'text-anchor="middle">{escape(entity.text)}</text>'
        )
    if entity.kind == "insert" and entity.position:
        return (
            f'<circle class="bg-block" cx="{entity.position.x:.3f}" '
            f'cy="{sy(entity.position.y):.3f}" r="80"/>'
        )
    return ""


def _render_room(room: Room, sy, points_attr) -> str:
    centroid = room.bbox.center
    name = room.name or f"Room {room.id}"
    label = f"{name} · {room.area_m2:.2f} m2"
    return (
        f'<polygon class="room" data-room-id="{escape(room.id)}" '
        f'points="{points_attr(room.boundary)}"><title>{escape(room.id)}</title></polygon>'
        f'<text class="room-label" x="{centroid.x:.3f}" y="{sy(centroid.y):.3f}" '
        f'font-size="{DEFAULT_TEXT_MM:.1f}" text-anchor="middle">{escape(label)}</text>'
    )


def _render_shaft(shaft: Shaft, sy) -> str:
    box = shaft.bbox
    return (
        f'<rect class="shaft" x="{box.minx:.3f}" y="{sy(box.maxy):.3f}" '
        f'width="{box.width:.3f}" height="{box.height:.3f}"><title>{escape(shaft.id)}</title></rect>'
    )


def _render_fixture(fixture: Fixture, sy) -> str:
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


def _layer_class(layer: str) -> str:
    lowered = layer.lower()
    if "wall" in lowered:
        return "wall"
    if "room" in lowered:
        return "room-outline"
    if "door" in lowered:
        return "door-line"
    if "shaft" in lowered or "duct" in lowered:
        return "shaft-line"
    return "misc"


def _style() -> str:
    return """<style>
  .bg { vector-effect: non-scaling-stroke; }
  .wall { stroke: #1f2937; fill: none; stroke-width: 40; stroke-linecap: round; }
  .room-outline { stroke: #cbd5e1; fill: none; stroke-width: 18; }
  .misc { stroke: #d1d5db; fill: none; stroke-width: 12; }
  .door-line { stroke: #b45309; fill: none; stroke-width: 20; }
  .shaft-line { stroke: #4f46e5; fill: none; stroke-width: 20; stroke-dasharray: 60 40; }
  .bg-label { fill: #94a3b8; font-family: ui-sans-serif, system-ui, sans-serif; }
  .bg-block { fill: #e5e7eb; stroke: #9ca3af; stroke-width: 12; }
  .room { fill: #f8fafc; stroke: #cbd5e1; stroke-width: 18; }
  .room-label { fill: #475569; font-family: ui-sans-serif, system-ui, sans-serif; }
  .door { fill: #fef3c7; stroke: #b45309; stroke-width: 18; }
  .shaft { fill: #eef2ff; stroke: #4f46e5; stroke-width: 18; stroke-dasharray: 60 40; }
  .fixture { fill: #dbeafe; stroke: #2563eb; stroke-width: 22; }
  .fixture-WC { fill: #e0f2fe; }
  .fixture-SHOWER { fill: #eff6ff; }
  .fixture-label { fill: #1d4ed8; font-family: ui-sans-serif, system-ui, sans-serif; font-weight: 600; }
  .pipe { fill: none; stroke-width: 55; stroke-linecap: round; stroke-linejoin: round; }
  .pipe-SOIL { stroke: #dc2626; }
  .pipe-WASTE { stroke: #d97706; }
  .pipe-VENT { stroke: #16a34a; }
  .pipe-label { fill: #7f1d1d; font-family: ui-sans-serif, system-ui, sans-serif; font-weight: 600; }
  .stack { fill: #fee2e2; stroke: #dc2626; stroke-width: 24; }
</style>"""
