from __future__ import annotations

from pathlib import Path

import ezdxf

from core.geometry import Point
from core.models import Building, Design, System

LAYERS = {
    "P-ROOM": 8,
    "P-SOIL": 1,
    "P-WASTE": 30,
    "P-VENT": 3,
    "P-FIXTURE": 5,
    "P-STACK": 1,
    "P-TEXT": 7,
}


def export_design(
    building: Building,
    design: Design,
    source_path: str | Path,
    target_path: str | Path,
) -> str:
    source = Path(source_path)
    if not source.exists():
        raise FileNotFoundError(f"Source drawing not found: {source}")
    doc = ezdxf.readfile(source)
    scale = building.source_scale or 1.0
    for name, color in LAYERS.items():
        if name not in doc.layers:
            doc.layers.add(name, color=color)

    msp = doc.modelspace()
    room = building.room(design.room_id)
    msp.add_lwpolyline(
        [(point.x / scale, point.y / scale) for point in room.boundary],
        close=True,
        dxfattribs={"layer": "P-ROOM"},
    )

    for pipe in design.pipes:
        msp.add_lwpolyline(
            [(point.x / scale, point.y / scale) for point in pipe.points],
            dxfattribs={"layer": _pipe_layer(pipe.system)},
        )
        label = _midpoint(pipe.points)
        _text(
            msp,
            f"{pipe.id} {pipe.diameter_mm:g}mm",
            label.x / scale,
            label.y / scale + 120 / scale,
            scale,
            height=120,
        )

    for fixture in design.fixtures:
        box = fixture.bbox
        msp.add_lwpolyline(
            [
                (box.minx / scale, box.miny / scale),
                (box.maxx / scale, box.miny / scale),
                (box.maxx / scale, box.maxy / scale),
                (box.minx / scale, box.maxy / scale),
            ],
            close=True,
            dxfattribs={"layer": "P-FIXTURE"},
        )
        _text(
            msp,
            fixture.type.value,
            fixture.position.x / scale,
            fixture.position.y / scale,
            scale,
            height=100,
        )

    msp.add_circle(
        (design.stack.position.x / scale, design.stack.position.y / scale),
        150 / scale,
        dxfattribs={"layer": "P-STACK"},
    )
    _text(
        msp,
        f"STACK {design.stack.id}",
        design.stack.position.x / scale + 250 / scale,
        design.stack.position.y / scale,
        scale,
        height=110,
    )

    note_x = room.bbox.minx / scale
    note_y = room.bbox.maxy / scale + 500 / scale
    notes = [
        f"FLOWLINE DESIGN - {design.profile_id}",
        f"Layout {design.layout_id or 'manual'} - engineer review required",
        "POC rule pack; not a compliance certificate",
    ]
    for index, note in enumerate(notes):
        _text(msp, note, note_x, note_y - index * 220 / scale, scale, height=120)

    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(target)
    return str(target)


def _pipe_layer(system: System) -> str:
    return {
        System.SOIL: "P-SOIL",
        System.WASTE: "P-WASTE",
        System.VENT: "P-VENT",
    }.get(system, "P-SOIL")


def _midpoint(points: list[Point]) -> Point:
    if not points:
        return Point(x=0, y=0)
    return points[len(points) // 2]


def _text(msp, text: str, x: float, y: float, scale: float, height: float = 120) -> None:
    entity = msp.add_text(
        str(text),
        dxfattribs={"layer": "P-TEXT", "height": max(height / scale, 1e-6)},
    )
    entity.set_placement((x, y))
