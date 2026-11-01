from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import ezdxf
from ezdxf.enums import TextEntityAlignment

from core.fixtures import connections_for, spec_for
from core.geometry import BBox, Point, bbox
from core.layout import _front_distance, _side_distance
from core.models import (
    SHEET_PRESETS_MM,
    Design,
    DrawingCheck,
    FixtureType,
    PlumbingItemType,
    Severity,
    SheetSpec,
    SupplySystem,
)
from core.rules.engine import RuleProfile

PLAN_LAYERS = [
    "P-ROOM",
    "P-SOIL",
    "P-WASTE",
    "P-VENT",
    "P-COLD",
    "P-HOT",
    "P-FIXTURE",
    "P-STACK",
    "P-TEXT",
    "P-DIM",
    "P-TAG",
    "P-LEADER",
    "P-SCHEDULE",
    "P-TITLE",
    "P-VIEWPORT",
    "P-NOTES",
    "P-LEGEND",
    "P-EQUIPMENT",
    "P-CLEANOUT",
]
LAYER_COLORS = {
    "P-ROOM": 8,
    "P-SOIL": 1,
    "P-WASTE": 30,
    "P-VENT": 3,
    "P-COLD": 5,
    "P-HOT": 1,
    "P-FIXTURE": 5,
    "P-STACK": 1,
    "P-TEXT": 7,
    "P-DIM": 8,
    "P-TAG": 7,
    "P-LEADER": 8,
    "P-SCHEDULE": 7,
    "P-TITLE": 7,
    "P-VIEWPORT": 8,
    "P-NOTES": 7,
    "P-LEGEND": 7,
    "P-EQUIPMENT": 6,
    "P-CLEANOUT": 2,
}
BLOCK_NAMES = {
    FixtureType.WC: "FL-WC",
    FixtureType.BASIN: "FL-BASIN",
    FixtureType.SHOWER: "FL-SHOWER",
    FixtureType.FLOOR_DRAIN: "FL-FLOOR-DRAIN",
    FixtureType.KITCHEN_SINK: "FL-KITCHEN-SINK",
}
ITEM_BLOCKS = {
    PlumbingItemType.WATER_HEATER: "FL-WATER-HEATER",
    PlumbingItemType.EXPANSION_TANK: "FL-EXPANSION-TANK",
    PlumbingItemType.MAIN_SHUTOFF: "FL-VALVE",
    PlumbingItemType.FIXTURE_STOP: "FL-FIXTURE-STOP",
    PlumbingItemType.CHECK_VALVE: "FL-CHECK-VALVE",
    PlumbingItemType.BACKFLOW_PREVENTER: "FL-CHECK-VALVE",
    PlumbingItemType.PRESSURE_REDUCING_VALVE: "FL-VALVE",
    PlumbingItemType.CLEANOUT: "FL-CLEANOUT",
    PlumbingItemType.TRAP_PRIMER: "FL-TRAP-PRIMER",
    PlumbingItemType.VENT_TERMINATION: "FL-VENT-TERMINAL",
    PlumbingItemType.AIR_ADMITTANCE_VALVE: "FL-AAV",
}


@dataclass
class SheetResult:
    dxf_path: Path
    svg_paths: list[Path]
    pdf_path: Path
    pages: int
    scale_used: float
    layout_names: list[str]
    review: list[DrawingCheck] = field(default_factory=list)


def prepare_sheet(
    building,
    design: Design,
    profile: RuleProfile,
    source_path: Path,
    out_dir: Path,
    *,
    project_name: str | None = None,
) -> SheetResult:
    doc, layout_names, meta = build_sheet(
        building, design, profile, source_path, project_name=project_name
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    dxf_path = out_dir / "sheet.dxf"
    doc.saveas(dxf_path)
    svg_paths = render_svgs(doc, layout_names, meta["sheet"], out_dir)
    pdf_path = render_pdf(doc, layout_names, meta["sheet"], out_dir / "sheet.pdf")
    review = review_sheet(doc, design, profile, layout_names, meta)
    return SheetResult(
        dxf_path=dxf_path,
        svg_paths=svg_paths,
        pdf_path=pdf_path,
        pages=meta["pages"],
        scale_used=meta["scale_used"],
        layout_names=layout_names,
        review=review,
    )


def build_sheet(
    building,
    design: Design,
    profile: RuleProfile,
    source_path: Path,
    *,
    project_name: str | None = None,
) -> tuple[ezdxf.document.Drawing, list[str], dict]:
    source = Path(source_path)
    if not source.exists():
        raise FileNotFoundError(f"Source drawing not found: {source}")
    doc = ezdxf.readfile(source)
    _clean_source_annotations(doc)
    spec = design.sheet
    width, height = sheet_dimensions(spec)
    source_scale = building.source_scale or 1.0

    _ensure_layers(doc)
    _ensure_linetypes(doc)
    _add_blocks(doc, source_scale)
    schedule_rows = (
        len(design.fixtures)
        + len(design.pipes)
        + len(design.vent_pipes)
        + len(design.supply_pipes)
    )
    page_count = 2 if width * height < 110_000 or schedule_rows > 24 else 1
    plan_rect = _plan_rect(width, height, page_count)
    scale_used = _scale_for(design, building, spec.scale, plan_rect)
    _ensure_dimstyle(doc, scale_used, source_scale)
    _add_model_entities(doc, design, source_scale, scale_used)
    _add_dimensions(doc, building, design, source_scale, scale_used)
    layout_names = _add_paper_pages(
        doc,
        building,
        design,
        profile,
        spec,
        width,
        height,
        page_count,
        plan_rect,
        scale_used,
        source_scale,
        project_name or source.stem,
    )
    meta = {
        "sheet": spec,
        "width": width,
        "height": height,
        "pages": page_count,
        "scale_used": scale_used,
    }
    return doc, layout_names, meta


def sheet_dimensions(spec: SheetSpec) -> tuple[float, float]:
    if spec.preset != "CUSTOM" and spec.preset in SHEET_PRESETS_MM:
        width, height = SHEET_PRESETS_MM[spec.preset]
    else:
        width, height = spec.width_mm, spec.height_mm
    if spec.orientation == "portrait" and width > height:
        width, height = height, width
    elif spec.orientation != "portrait" and width < height:
        width, height = height, width
    return max(100.0, width), max(100.0, height)


def _plan_rect(width: float, height: float, pages: int) -> tuple[float, float, float, float]:
    margin = 8.0
    title_h = 27.0
    legend_h = 22.0
    if pages == 1:
        right_w = min(155.0, max(105.0, width * 0.33))
        x0 = margin
        x1 = width - right_w - margin * 1.5
        y0 = margin + title_h + 6
        y1 = height - margin
        return x0, y0, x1, y1
    x0 = margin
    x1 = width - margin
    y0 = margin + title_h + legend_h + 12
    y1 = height - margin
    return x0, y0, x1, y1


def _scale_for(
    design: Design, building, requested: float, rect: tuple[float, float, float, float]
) -> float:
    box = _design_bbox(building, design)
    paper_w = max(1.0, rect[2] - rect[0])
    paper_h = max(1.0, rect[3] - rect[1])
    required = max(box.width / (paper_w * 0.88), box.height / (paper_h * 0.88))
    # Fill the available plan area instead of leaving a tiny 1:50 drawing on a large sheet.
    return max(10.0, math.ceil(required / 5.0) * 5.0)


def _design_stacks(design: Design) -> list:
    stacks = list(design.stacks) or [design.stack]
    if design.stack.id not in {stack.id for stack in stacks}:
        stacks.insert(0, design.stack)
    return stacks


def _design_vent_stacks(design: Design) -> list:
    stacks = list(design.vent_stacks)
    if design.vent_stack is not None and design.vent_stack.id not in {
        stack.id for stack in stacks
    }:
        stacks.insert(0, design.vent_stack)
    return stacks


def _design_bbox(building, design: Design) -> BBox:
    room_ids = design.room_ids or [design.room_id]
    points: list[Point] = []
    for room_id in room_ids:
        points.extend(building.room(room_id).boundary)
    for fixture in design.fixtures:
        box = fixture.bbox
        points.extend(
            [
                Point(x=box.minx, y=box.miny),
                Point(x=box.maxx, y=box.miny),
                Point(x=box.maxx, y=box.maxy),
                Point(x=box.minx, y=box.maxy),
            ]
        )
    for pipe in [*design.pipes, *design.vent_pipes]:
        points.extend(pipe.points)
    for pipe in design.supply_pipes:
        points.extend(pipe.points)
    for item in design.plumbing_items:
        points.append(item.position)
    points.extend(stack.position for stack in _design_stacks(design))
    points.extend(stack.position for stack in _design_vent_stacks(design))
    if design.water_source:
        points.append(design.water_source.position)
    box = bbox(points)
    pad = max(250.0, max(box.width, box.height) * 0.08)
    return BBox(box.minx - pad, box.miny - pad, box.maxx + pad, box.maxy + pad)


def _clean_source_annotations(doc) -> None:
    for entity in list(doc.modelspace()):
        if entity.dxftype() in ("TEXT", "MTEXT") and getattr(entity.dxf, "layer", "") in (
            "A-TEXT",
            "A-ANNO",
            "A-ANNOTATION",
        ):
            doc.modelspace().delete_entity(entity)


def _ensure_layers(doc) -> None:
    for name, color in LAYER_COLORS.items():
        if name not in doc.layers:
            doc.layers.add(name, color=color)


def _ensure_linetypes(doc) -> None:
    if "DASHED" not in doc.linetypes:
        try:
            doc.linetypes.add("DASHED", pattern=[0.6, 0.3, -0.3])
        except Exception:
            pass


def _ensure_dimstyle(doc, scale_used: float, source_scale: float) -> None:
    name = "FL-DIM"
    if name not in doc.dimstyles:
        dimstyle = doc.dimstyles.new(name)
    else:
        dimstyle = doc.dimstyles.get(name)
    text_h = 2.5 * scale_used / source_scale
    dimstyle.dxf.dimtxt = text_h
    dimstyle.dxf.dimasz = 2.0 * scale_used / source_scale
    dimstyle.dxf.dimexo = 1.0 * scale_used / source_scale
    dimstyle.dxf.dimexe = 1.5 * scale_used / source_scale
    dimstyle.dxf.dimdec = 0
    dimstyle.dxf.dimlfac = source_scale
    dimstyle.dxf.dimtad = 1


def _add_blocks(doc, source_scale: float) -> None:
    for fixture_type, name in BLOCK_NAMES.items():
        if name in doc.blocks:
            continue
        block = doc.blocks.new(name=name)
        spec = spec_for(fixture_type)
        w, d = spec.width_mm, spec.depth_mm
        block.add_lwpolyline(
            [(-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)],
            close=True,
        )
        if fixture_type in (FixtureType.WC, FixtureType.BASIN):
            block.add_ellipse(
                center=(0, 0),
                major_axis=(w * 0.32, 0),
                ratio=0.7,
            )
        elif fixture_type == FixtureType.SHOWER:
            block.add_line((-w / 2, -d / 2), (w / 2, d / 2))
            block.add_line((-w / 2, d / 2), (w / 2, -d / 2))
        elif fixture_type == FixtureType.FLOOR_DRAIN:
            block.add_circle((0, 0), w / 2)
            block.add_circle((0, 0), w / 5)

    _simple_block(doc, "FL-STACK", [("circle", (0, 0), 80)])
    _simple_block(doc, "FL-VENT-STACK", [("circle", (0, 0), 60)])
    _simple_block(doc, "FL-WATER-SOURCE", [("rect", 500, 500)])
    _simple_block(doc, "FL-WATER-HEATER", [("rect", 520, 520)])
    _simple_block(doc, "FL-EXPANSION-TANK", [("circle", (0, 0), 150)])
    _simple_block(doc, "FL-CLEANOUT", [("rect", 120, 120)])
    _simple_block(doc, "FL-VALVE", [("diamond", 140, 140)])
    _simple_block(doc, "FL-CHECK-VALVE", [("diamond", 120, 120)])
    _simple_block(doc, "FL-FIXTURE-STOP", [("circle", (0, 0), 55)])
    _simple_block(doc, "FL-TRAP-PRIMER", [("circle", (0, 0), 80)])
    _simple_block(doc, "FL-VENT-TERMINAL", [("triangle", 160, 160)])
    _simple_block(doc, "FL-AAV", [("circle", (0, 0), 65)])


def _simple_block(doc, name: str, shapes: list[tuple]) -> None:
    if name in doc.blocks:
        return
    block = doc.blocks.new(name=name)
    for shape in shapes:
        kind = shape[0]
        if kind == "circle":
            block.add_circle(shape[1], shape[2])
        elif kind == "rect":
            w, h = shape[1], shape[2]
            block.add_lwpolyline(
                [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)],
                close=True,
            )
        elif kind == "diamond":
            w, h = shape[1], shape[2]
            block.add_lwpolyline(
                [(0, -h / 2), (w / 2, 0), (0, h / 2), (-w / 2, 0)],
                close=True,
            )
        elif kind == "triangle":
            w, h = shape[1], shape[2]
            block.add_lwpolyline(
                [(-w / 2, -h / 2), (w / 2, -h / 2), (0, h / 2)],
                close=True,
            )


def _add_model_entities(doc, design: Design, source_scale: float, scale_used: float) -> None:
    msp = doc.modelspace()
    for pipe in design.pipes:
        _polyline(msp, pipe.points, source_scale, "P-SOIL" if pipe.system.value == "SOIL" else "P-WASTE")
    for pipe in design.vent_pipes:
        _polyline(msp, pipe.points, source_scale, "P-VENT", linetype="DASHED")
    for pipe in design.supply_pipes:
        layer = "P-HOT" if pipe.system == SupplySystem.HOT else "P-COLD"
        _polyline(msp, pipe.points, source_scale, layer)
    for fixture in design.fixtures:
        block = BLOCK_NAMES.get(fixture.type)
        if block:
            msp.add_blockref(
                block,
                insert=(fixture.position.x / source_scale, fixture.position.y / source_scale),
                dxfattribs={
                    "layer": "P-FIXTURE",
                    "xscale": 1 / source_scale,
                    "yscale": 1 / source_scale,
                    "rotation": fixture.rotation_deg,
                },
            )
        _model_text(
            msp,
            fixture.id,
            fixture.position.x / source_scale + 190 / source_scale,
            fixture.position.y / source_scale - 190 / source_scale,
            scale_used / source_scale * 0.55,
            layer="P-TAG",
        )
    for stack in _design_stacks(design):
        msp.add_blockref(
            "FL-STACK",
            insert=(stack.position.x / source_scale, stack.position.y / source_scale),
            dxfattribs={"layer": "P-STACK", "xscale": 1 / source_scale, "yscale": 1 / source_scale},
        )
        _model_text(
            msp,
            stack.id,
            stack.position.x / source_scale + 180 / source_scale,
            stack.position.y / source_scale + 180 / source_scale,
            scale_used / source_scale,
            layer="P-TAG",
        )
    for vent_stack in _design_vent_stacks(design):
        msp.add_blockref(
            "FL-VENT-STACK",
            insert=(vent_stack.position.x / source_scale, vent_stack.position.y / source_scale),
            dxfattribs={"layer": "P-STACK", "xscale": 1 / source_scale, "yscale": 1 / source_scale},
        )
        _model_text(msp, f"VENT {vent_stack.id}", vent_stack.position.x / source_scale + 180 / source_scale, vent_stack.position.y / source_scale, scale_used / source_scale, layer="P-TAG")
    if design.water_source:
        msp.add_blockref(
            "FL-WATER-SOURCE",
            insert=(design.water_source.position.x / source_scale, design.water_source.position.y / source_scale),
            dxfattribs={"layer": "P-EQUIPMENT", "xscale": 1 / source_scale, "yscale": 1 / source_scale},
        )
        _model_text(msp, "WATER SOURCE", design.water_source.position.x / source_scale, design.water_source.position.y / source_scale - 360 / source_scale, scale_used / source_scale, layer="P-TAG")
    for item in design.plumbing_items:
        block = ITEM_BLOCKS.get(item.type)
        if block:
            msp.add_blockref(
                block,
                insert=(item.position.x / source_scale, item.position.y / source_scale),
                dxfattribs={"layer": "P-EQUIPMENT" if item.type in (
                    PlumbingItemType.WATER_HEATER,
                    PlumbingItemType.EXPANSION_TANK,
                    PlumbingItemType.MAIN_SHUTOFF,
                ) else "P-CLEANOUT", "xscale": 1 / source_scale, "yscale": 1 / source_scale},
            )
        _model_text(msp, item.tag or item.type.value, item.position.x / source_scale + 100 / source_scale, item.position.y / source_scale + 100 / source_scale, scale_used / source_scale * 0.72, layer="P-TAG")
    for index, pipe in enumerate(design.pipes):
        _pipe_tag(msp, pipe, source_scale, scale_used, "DRAIN", index)
    for index, pipe in enumerate(design.vent_pipes):
        _pipe_tag(msp, pipe, source_scale, scale_used, "VENT", index)
    for index, pipe in enumerate(design.supply_pipes):
        _pipe_tag(msp, pipe, source_scale, scale_used, "SUPPLY", index)


def _polyline(msp, points, source_scale: float, layer: str, linetype: str | None = None) -> None:
    msp.add_lwpolyline(
        [(point.x / source_scale, point.y / source_scale) for point in points],
        dxfattribs={"layer": layer, **({"linetype": linetype} if linetype else {})},
    )


def _model_text(msp, text: str, x: float, y: float, scale_used: float, *, layer: str) -> None:
    entity = msp.add_text(
        str(text),
        dxfattribs={"layer": layer, "height": max(2.2 * scale_used, 0.01)},
    )
    entity.set_placement((x, y), align=TextEntityAlignment.MIDDLE_LEFT)


def _pipe_tag(
    msp,
    pipe,
    source_scale: float,
    scale_used: float,
    kind: str,
    index: int,
) -> None:
    if not pipe.points:
        return
    mid = pipe.points[len(pipe.points) // 2]
    label = pipe.id
    offset = 110.0 + (index % 4) * 85.0
    _model_text(
        msp,
        label,
        mid.x / source_scale,
        mid.y / source_scale + offset / source_scale,
        scale_used / source_scale * 0.55,
        layer="P-TAG",
    )


def _add_dimensions(doc, building, design: Design, source_scale: float, scale_used: float) -> None:
    msp = doc.modelspace()
    room_ids = design.room_ids or [design.room_id]
    offset = max(300.0, 2.5 * scale_used)

    def point(x, y):
        return (x / source_scale, y / source_scale)

    try:
        for room_id in room_ids:
            room = building.room(room_id)
            box = room.bbox
            msp.add_linear_dim(
                base=point((box.minx + box.maxx) / 2, box.miny - offset),
                p1=point(box.minx, box.miny),
                p2=point(box.maxx, box.miny),
                angle=0,
                dimstyle="FL-DIM",
            ).render()
            msp.add_linear_dim(
                base=point(box.maxx + offset, (box.miny + box.maxy) / 2),
                p1=point(box.maxx, box.miny),
                p2=point(box.maxx, box.maxy),
                angle=90,
                dimstyle="FL-DIM",
            ).render()
        for fixture in design.fixtures:
            if fixture.type == FixtureType.FLOOR_DRAIN:
                continue
            room = building.room(fixture.room_id or design.room_id)
            box = room.bbox
            fbox = fixture.bbox
            side = _side_distance(fixture, box)
            if side > 0:
                left = fixture.position.x < (box.minx + box.maxx) / 2
                base_y = fbox.miny - offset * 0.6
                msp.add_linear_dim(
                    base=point((box.minx + fbox.minx) / 2 if left else (box.maxx + fbox.maxx) / 2, base_y),
                    p1=point(box.minx if left else box.maxx, fbox.miny),
                    p2=point(fbox.minx if left else fbox.maxx, fbox.miny),
                    angle=0,
                    dimstyle="FL-DIM",
                ).render()
            front = _front_distance(fixture, box)
            if front > 0:
                base_x = fbox.maxx + offset * 0.5
                msp.add_linear_dim(
                    base=point(base_x, (min(box.miny, fbox.miny) + max(box.maxy, fbox.maxy)) / 2),
                    p1=point(fbox.maxx, fbox.miny),
                    p2=point(fbox.maxx, fbox.maxy),
                    angle=90,
                    dimstyle="FL-DIM",
                ).render()
    except Exception:
        # Dimensions are important but should never prevent a sheet export.
        pass


def _add_paper_pages(
    doc,
    building,
    design: Design,
    profile: RuleProfile,
    spec: SheetSpec,
    width: float,
    height: float,
    pages: int,
    plan_rect,
    scale_used: float,
    source_scale: float,
    project_name: str,
) -> list[str]:
    names: list[str] = []
    for page in range(1, pages + 1):
        name = f"FL-{spec.sheet_number.replace(' ', '-')}-{page}"
        layout = doc.layouts.new(name)
        layout.page_setup(size=(width, height), margins=(0, 0, 0, 0), units="mm")
        names.append(name)
        _page_border(layout, width, height)
        _title_block(layout, spec, profile, width, margin=8.0, page=page, pages=pages, scale_used=scale_used, project_name=project_name)
        if page == 1:
            _draw_plan_page(
                layout,
                building,
                design,
                profile,
                spec,
                width,
                height,
                plan_rect,
                scale_used,
                source_scale,
                pages,
            )
        else:
            _draw_schedule_page(layout, design, profile, spec, width, height, scale_used)
    return names


def _page_border(layout, width: float, height: float) -> None:
    margin = 8.0
    layout.add_lwpolyline(
        [(margin, margin), (width - margin, margin), (width - margin, height - margin), (margin, height - margin)],
        close=True,
        dxfattribs={"layer": "P-TITLE"},
    )


def _title_block(layout, spec, profile, width, *, margin, page, pages, scale_used, project_name) -> None:
    block_w = min(155.0, max(105.0, width * 0.38))
    block_h = 27.0
    x = width - margin - block_w
    y = margin
    _box(layout, x, y, block_w, block_h, "P-TITLE")
    layout.add_line((x, y + 8), (x + block_w, y + 8), dxfattribs={"layer": "P-TITLE"})
    layout.add_line(
        (x + block_w * 0.58, y + 8),
        (x + block_w * 0.58, y + block_h),
        dxfattribs={"layer": "P-TITLE"},
    )
    _paper_text(layout, project_name, x + 2, y + block_h - 4.5, 2.6, "P-TITLE")
    _paper_text(layout, spec.title, x + 2, y + block_h - 9.0, 2.0, "P-TITLE")
    _paper_text(
        layout,
        f"SHEET {spec.sheet_number} / {page} OF {pages}",
        x + 2,
        y + 14.5,
        1.8,
        "P-TITLE",
    )
    _paper_text(layout, f"STANDARD {profile.name}", x + 2, y + 10.8, 1.4, "P-TITLE")
    _paper_text(layout, f"SCALE 1:{scale_used:g}", x + block_w * 0.6, y + 19, 1.9, "P-TITLE")
    _paper_text(
        layout,
        f"REV {spec.revision}   {date.today().isoformat()}",
        x + block_w * 0.6,
        y + 15,
        1.5,
        "P-TITLE",
    )
    _paper_text(
        layout,
        f"DRAWN {spec.drawn_by}   CHECKED {spec.checked_by or '-'}",
        x + 2,
        y + 3.4,
        1.4,
        "P-TITLE",
    )


def _draw_plan_page(layout, building, design, profile, spec, width, height, rect, scale_used, source_scale, pages) -> None:
    x0, y0, x1, y1 = rect
    plan_w = max(50.0, x1 - x0)
    plan_h = max(50.0, y1 - y0)
    if pages == 1:
        screen_right = width - min(155.0, max(105.0, width * 0.33)) - 8
        plan_w = max(80.0, screen_right - x0 - 8)
    extent = _design_bbox(building, design)
    draw_w = extent.width / scale_used * 1.1
    draw_h = extent.height / scale_used * 1.1
    view_w = min(plan_w, max(60.0, draw_w))
    view_h = min(plan_h, max(50.0, draw_h))
    cx = x0 + plan_w / 2
    cy = y0 + plan_h / 2
    layout.add_viewport(
        center=(cx, cy),
        size=(view_w, view_h),
        view_center_point=(
            extent.center.x / source_scale,
            extent.center.y / source_scale,
        ),
        view_height=view_h * scale_used / source_scale,
        dxfattribs={"layer": "P-VIEWPORT"},
    )
    layout.add_lwpolyline(
        [
            (cx - view_w / 2, cy - view_h / 2),
            (cx + view_w / 2, cy - view_h / 2),
            (cx + view_w / 2, cy + view_h / 2),
            (cx - view_w / 2, cy + view_h / 2),
        ],
        close=True,
        dxfattribs={"layer": "P-VIEWPORT"},
    )
    _paper_text(
        layout,
        f"PLUMBING PLAN  1:{scale_used:g}",
        cx - view_w / 2 + 2,
        cy + view_h / 2 - 4,
        2.4,
        "P-TITLE",
        bold=True,
    )
    if pages == 1:
        _legend(layout, x0 + 2, y0 + 2, 70, 34)
        _right_column(layout, design, profile, width, height, scale_used)
    else:
        _legend(layout, x0 + 2, 8.5, 70, 22)
        _notes(layout, spec, x0 + 80, 8.5, width - x0 - 90)


def _draw_schedule_page(layout, design, profile, spec, width, height, scale_used) -> None:
    x = 14.0
    y = height - 18.0
    if width >= 300:
        column = (width - 36.0) / 2
        left_y = _fixture_table(layout, design, profile, x, y, column)
        right_y = _pipe_table(layout, design, x + column + 8, y, column)
        y = min(left_y, right_y) - 10
        y = _equipment_table(layout, design, x, y, width - 28.0)
    else:
        y = _fixture_table(layout, design, profile, x, y, width - 28.0)
        y -= 10
        y = _pipe_table(layout, design, x, y, width - 28.0)
        y -= 10
        y = _equipment_table(layout, design, x, y, width - 28.0)
    _riser_diagram(layout, design, x, max(48, y - 55), width - 28, 45)
    _notes(layout, spec, x, 44, width - 28)


def _right_column(layout, design, profile, width, height, scale_used) -> None:
    right_w = min(155.0, max(105.0, width * 0.33))
    x = width - right_w - 8
    y = height - 18
    y = _fixture_table(layout, design, profile, x, y, right_w)
    y -= 8
    y = _pipe_table(layout, design, x, y, right_w)
    y -= 8
    _riser_diagram(layout, design, x, max(55, y - 52), right_w, 42)


def _fixture_table(layout, design, profile, x, y, width) -> float:
    headers = ["ROOM", "TAG", "FIXTURE", "COLD", "HOT", "DRAIN", "VENT"]
    rows = []
    for fixture in design.fixtures:
        cold = profile.supply.cold_fixture_mm.get(fixture.type.value)
        hot = profile.supply.hot_fixture_mm.get(fixture.type.value)
        drain = profile.pipe_for(fixture.type).diameter_mm
        rows.append(
            [
                fixture.room_id or design.room_id,
                fixture.id,
                fixture.type.value.replace("_", " "),
                f"{cold:g}mm" if cold else "-",
                f"{hot:g}mm" if hot else "-",
                f"{drain:g}mm",
                f"{profile.vent.min_diameter_mm:g}mm",
            ]
        )
    return _table(layout, x, y, width, "FIXTURE SCHEDULE", headers, rows)


def _pipe_table(layout, design, x, y, width) -> float:
    headers = ["ROOM", "TAG", "SYSTEM", "SIZE", "SLOPE/LEN", "MATERIAL"]
    rows = []
    for pipe in design.pipes:
        slope = f"{pipe.slope:g}" if pipe.slope is not None else "-"
        rows.append([
            pipe.room_id or design.room_id,
            pipe.id,
            pipe.system.value,
            f"{pipe.diameter_mm:g}mm",
            slope,
            "PVC",
        ])
    for pipe in design.vent_pipes:
        rows.append([
            pipe.room_id or design.room_id,
            pipe.id,
            "VENT",
            f"{pipe.diameter_mm:g}mm",
            "0",
            "PVC",
        ])
    for pipe in design.supply_pipes:
        rows.append([
            pipe.room_id or design.room_id,
            pipe.id,
            pipe.system.value,
            f"{pipe.diameter_mm:g}mm",
            "-",
            pipe.material,
        ])
    return _table(layout, x, y, width, "PIPE SCHEDULE", headers, rows)


def _equipment_table(layout, design, x, y, width) -> float:
    headers = ["ROOM", "TAG", "ITEM", "SIZE", "SYSTEM"]
    rows = []
    for item in design.plumbing_items:
        rows.append([
            item.room_id or design.room_id,
            item.tag or item.id,
            item.type.value.replace("_", " "),
            item.size or "-",
            item.system or "-",
        ])
    return _table(layout, x, y, width, "EQUIPMENT / VALVES", headers, rows)


def _table(layout, x, y_top, width, title, headers, rows) -> float:
    row_h = 4.2
    header_h = 4.6
    title_h = 5.0
    visible = max(1, int((y_top - 40 - title_h - header_h) / row_h))
    rows = rows[:visible]
    _paper_text(layout, title, x, y_top, 2.4, "P-SCHEDULE", bold=True)
    y = y_top - title_h
    cols = len(headers)
    col_w = width / cols
    _row_rect(layout, x, y - header_h, width, header_h, cols, col_w)
    for index, header in enumerate(headers):
        _paper_text(layout, header, x + index * col_w + 1.2, y - header_h + 1.3, 1.6, "P-SCHEDULE", bold=True)
    y -= header_h
    for row in rows:
        _row_rect(layout, x, y - row_h, width, row_h, cols, col_w)
        for index, value in enumerate(row):
            _paper_text(layout, str(value), x + index * col_w + 1.2, y - row_h + 1.2, 1.5, "P-SCHEDULE")
        y -= row_h
    return y


def _row_rect(layout, x, y, width, height, cols, col_w) -> None:
    layout.add_lwpolyline(
        [(x, y), (x + width, y), (x + width, y + height), (x, y + height)],
        close=True,
        dxfattribs={"layer": "P-SCHEDULE"},
    )
    for index in range(1, cols):
        layout.add_line((x + index * col_w, y), (x + index * col_w, y + height), dxfattribs={"layer": "P-SCHEDULE"})


def _legend(layout, x, y, width, height) -> None:
    _box(layout, x, y, width, height, "P-LEGEND")
    _paper_text(layout, "LEGEND", x + 2, y + height - 4, 2.0, "P-LEGEND", bold=True)
    entries = [
        ("SOIL", "P-SOIL", ""),
        ("WASTE", "P-WASTE", ""),
        ("VENT", "P-VENT", "DASHED"),
        ("COLD WATER", "P-COLD", ""),
        ("HOT WATER", "P-HOT", ""),
    ]
    for index, (label, layer, linetype) in enumerate(entries):
        yy = y + height - 8 - index * 4.4
        layout.add_line((x + 2, yy), (x + 16, yy), dxfattribs={"layer": layer, **({"linetype": linetype} if linetype else {})})
        _paper_text(layout, label, x + 19, yy - 1.2, 1.6, "P-LEGEND")


def _notes(layout, spec, x, y, width) -> None:
    _paper_text(layout, "GENERAL NOTES", x, y + 10, 1.9, "P-NOTES", bold=True)
    notes = [
        "1. Verify all dimensions and clearances on site before installation.",
        "2. Provide access to valves, cleanouts, and the vent termination.",
        "3. Supply and vent routes are schematic; coordinate ceiling and wall voids.",
        "4. This is a POC rule-set drawing, not a compliance certificate.",
        *[f"{index + 5}. {note}" for index, note in enumerate(spec.notes[:3])],
    ]
    for index, note in enumerate(notes[:8]):
        _paper_text(layout, note, x, y + 6 - index * 3.5, 1.45, "P-NOTES")


def _riser_diagram(layout, design, x, y, width, height) -> None:
    _box(layout, x, y, width, height, "P-LEGEND")
    _paper_text(layout, "RISER DIAGRAM (SCHEMATIC)", x + 2, y + height - 4, 1.8, "P-LEGEND", bold=True)
    base_y = y + 5
    top_y = y + height - 9
    stacks = _design_stacks(design)
    vents = {item.stack_id: item for item in _design_vent_stacks(design)}
    column = (width * 0.58) / max(1, len(stacks))
    for index, stack in enumerate(stacks):
        soil_x = x + width * 0.18 + column * index
        vent = vents.get(stack.id)
        vent_x = soil_x + 5
        layout.add_line((soil_x, base_y), (soil_x, top_y), dxfattribs={"layer": "P-SOIL"})
        if vent is not None:
            layout.add_line(
                (vent_x, base_y),
                (vent_x, top_y),
                dxfattribs={"layer": "P-VENT", "linetype": "DASHED"},
            )
        _paper_text(layout, stack.id, soil_x - 2, top_y + 1, 1.2, "P-LEGEND")
        if vent is not None:
            _paper_text(layout, vent.id, vent_x + 1, top_y + 1, 1.0, "P-LEGEND")
        fixtures = [
            fixture
            for fixture in design.fixtures
            if design.stack_for_room(fixture.room_id or design.room_id).id == stack.id
        ]
        step = max(1.4, min(3.5, (top_y - base_y - 8) / max(1, len(fixtures))))
        for row, fixture in enumerate(fixtures):
            yy = base_y + 5 + row * step
            layout.add_line((soil_x, yy), (soil_x + 8, yy), dxfattribs={"layer": "P-WASTE"})
            _paper_text(layout, fixture.id, soil_x + 9, yy - 1, 0.8, "P-LEGEND")
    water_x = x + width * 0.76
    layout.add_line((water_x, base_y), (water_x, top_y), dxfattribs={"layer": "P-COLD"})
    layout.add_line((water_x + 5, base_y), (water_x + 5, top_y), dxfattribs={"layer": "P-HOT"})
    _paper_text(layout, "CW/HW", water_x - 2, top_y + 1, 1.2, "P-LEGEND")
    if design.water_source:
        _paper_text(layout, "WATER HEATER / SOURCE", water_x - 12, base_y - 2, 1.0, "P-LEGEND")


def _design_center(design: Design) -> Point:
    points = [stack.position for stack in _design_stacks(design)]
    for fixture in design.fixtures:
        points.append(fixture.position)
    for pipe in [*design.pipes, *design.vent_pipes]:
        points.extend(pipe.points)
    for pipe in design.supply_pipes:
        points.extend(pipe.points)
    for item in design.plumbing_items:
        points.append(item.position)
    points.extend(stack.position for stack in _design_vent_stacks(design))
    if design.water_source:
        points.append(design.water_source.position)
    return bbox(points).center


def _box(layout, x, y, w, h, layer) -> None:
    layout.add_lwpolyline(
        [(x, y), (x + w, y), (x + w, y + h), (x, y + h)],
        close=True,
        dxfattribs={"layer": layer},
    )


def _paper_text(layout, text: str, x, y, height, layer, bold=False) -> None:
    entity = layout.add_text(
        str(text),
        height=height,
        dxfattribs={"layer": layer},
    )
    entity.set_placement((x, y), align=TextEntityAlignment.LEFT)


def render_svgs(doc, layout_names: list[str], spec: SheetSpec, out_dir: Path) -> list[Path]:
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import BackgroundPolicy, Configuration
    from ezdxf.addons.drawing.layout import Margins, Page, Settings
    from ezdxf.addons.drawing.svg import SVGBackend

    width, height = sheet_dimensions(spec)
    paths = []
    for index, name in enumerate(layout_names, start=1):
        backend = SVGBackend()
        context = RenderContext(doc)
        frontend = Frontend(
            context,
            backend,
            config=Configuration(background_policy=BackgroundPolicy.WHITE),
        )
        layout = doc.layouts.get(name)
        frontend.draw_layout(layout)
        svg = backend.get_string(
            Page(width, height, margins=Margins(0, 0, 0, 0)),
            settings=Settings(fit_page=False, output_layers=False),
        )
        path = out_dir / f"sheet-{index}.svg"
        path.write_text(svg, encoding="utf-8")
        paths.append(path)
    return paths


def render_pdf(doc, layout_names: list[str], spec: SheetSpec, path: Path) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import BackgroundPolicy, Configuration
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    from matplotlib.backends.backend_pdf import PdfPages

    width, height = sheet_dimensions(spec)
    path.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(path) as pdf:
        for name in layout_names:
            fig = plt.figure(figsize=(width / 25.4, height / 25.4), dpi=120)
            axis = fig.add_axes((0, 0, 1, 1))
            axis.set_axis_off()
            backend = MatplotlibBackend(axis)
            frontend = Frontend(
                RenderContext(doc),
                backend,
                config=Configuration(background_policy=BackgroundPolicy.WHITE),
            )
            frontend.draw_layout(doc.layouts.get(name))
            pdf.savefig(fig)
            plt.close(fig)
    return path


def review_sheet(
    doc,
    design: Design,
    profile: RuleProfile,
    layout_names: list[str],
    meta: dict,
) -> list[DrawingCheck]:
    checks: list[DrawingCheck] = []

    def add(rule_id: str, ok: bool, message: str, severity: Severity = Severity.ERROR, affected=None):
        checks.append(
            DrawingCheck(
                rule_id=rule_id,
                severity=Severity.PASS if ok else severity,
                message=message,
                affected=affected or {},
            )
        )

    requires_vent = not design.fixtures or any(
        connections_for(fixture).vent is not None for fixture in design.fixtures
    )
    requires_water = not design.fixtures or any(
        connections_for(fixture).cold is not None
        or connections_for(fixture).hot is not None
        for fixture in design.fixtures
    )
    add(
        "SHEET_SERVICES",
        not requires_vent or bool(design.vent_pipes),
        "Vent routes are included in the sheet when fixtures need vents.",
    )
    add(
        "SHEET_WATER",
        not requires_water or bool(design.supply_pipes),
        "Hot/cold water routes are included in the sheet when fixtures need water.",
    )
    add("SHEET_EQUIPMENT", bool(design.plumbing_items), "Plumbing equipment/valves are scheduled.")
    for layer in PLAN_LAYERS:
        add("SHEET_LAYER", layer in doc.layers, f"Layer {layer} exists.", affected={"layer": layer})
    add(
        "SHEET_LAYOUTS",
        len(layout_names) == meta.get("pages"),
        f"{len(layout_names)} sheet layout(s) created.",
    )
    layouts = [doc.layouts.get(name) for name in layout_names]
    add(
        "SHEET_VIEWPORT",
        any(entity.dxftype() == "VIEWPORT" for layout in layouts for entity in layout),
        "Plan viewport is present.",
    )
    add(
        "SHEET_DIMENSIONS",
        any(entity.dxftype() == "DIMENSION" for entity in doc.modelspace()),
        "Construction dimensions are present.",
    )
    add(
        "SHEET_BLOCKS",
        sum(1 for entity in doc.modelspace() if entity.dxftype() == "INSERT") >= len(design.fixtures),
        "Fixture blocks are inserted.",
    )
    title_text = " ".join(
        entity.dxf.text
        for layout in layouts
        for entity in layout
        if entity.dxftype() == "TEXT"
    ).lower()
    add("SHEET_TITLE", "sheet" in title_text and "scale" in title_text, "Title block fields are present.")
    add(
        "SHEET_SCHEDULE",
        "schedule" in title_text,
        "Schedules are present.",
    )
    fixture_tags = [fixture.id for fixture in design.fixtures]
    model_text = " ".join(
        entity.dxf.text
        for entity in doc.modelspace()
        if entity.dxftype() == "TEXT"
    )
    add(
        "SHEET_FIXTURE_TAGS",
        all(tag in model_text for tag in fixture_tags),
        "Every fixture has a sheet tag.",
    )
    return checks


def sheet_counts(checks: list[DrawingCheck]) -> dict[str, int]:
    counts = {"PASS": 0, "WARNING": 0, "ERROR": 0}
    for check in checks:
        counts[check.severity.value] += 1
    return counts
