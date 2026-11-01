import re

import ezdxf

from core.dxf_import import import_dxf
from core.svg import render_svg


def _build_wall_plan(path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    for name in ("WALLS", "ROOMS", "ROOM_NAMES", "NOTES", "DOORS", "DIMENSIONS", "BOUNDARY"):
        doc.layers.add(name)
    msp = doc.modelspace()

    def wall(x1, y1, x2, y2):
        msp.add_lwpolyline(
            [(x1, y1), (x2, y1), (x2, y2), (x1, y2)],
            close=True,
            dxfattribs={"layer": "WALLS"},
        )

    wall(0, 0, 500, 200)
    wall(1500, 0, 6000, 200)
    wall(0, 3800, 6000, 4000)
    wall(0, 0, 200, 4000)
    wall(5800, 0, 6000, 4000)
    wall(2900, 200, 3100, 1800)
    wall(2900, 2600, 3100, 3800)

    msp.add_text(
        "BATHROOM", dxfattribs={"layer": "ROOM_NAMES", "height": 180}
    ).set_placement((1500, 2000))
    msp.add_text(
        "BEDROOM", dxfattribs={"layer": "ROOM_NAMES", "height": 180}
    ).set_placement((4500, 2000))
    msp.add_text(
        "Approx. 2.8 x 3.6 m", dxfattribs={"layer": "NOTES", "height": 100}
    ).set_placement((1500, 1750))
    msp.add_text(
        "TITLE BLOCK", dxfattribs={"layer": "NOTES", "height": 300}
    ).set_placement((8000, 3800))

    msp.add_line((500, 100), (500, 1100), dxfattribs={"layer": "DOORS"})
    msp.add_arc(
        (500, 100), 1000, 0, 90, dxfattribs={"layer": "DOORS"}
    )
    msp.add_line((0, -500), (6000, -500), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_line((7000, 0), (9000, 0), dxfattribs={"layer": "BOUNDARY"})

    doc.saveas(path)


def test_detects_rooms_from_wall_bands_and_labels(tmp_path):
    path = tmp_path / "wall_plan.dxf"
    _build_wall_plan(path)

    building = import_dxf(path)

    names = {room.name for room in building.rooms}
    assert names == {"BATHROOM", "BEDROOM"}
    assert len(building.rooms) == 2
    assert [room.name for room in building.wet_area_candidates()] == ["BATHROOM"]
    assert all(room.bbox.width > 1000 for room in building.rooms)


def test_preview_crops_annotation_block_and_scales_strokes(tmp_path):
    path = tmp_path / "wall_plan.dxf"
    _build_wall_plan(path)

    svg = render_svg(import_dxf(path))

    match = re.search(r'viewBox="([^"]+)"', svg)
    assert match is not None
    width = float(match.group(1).split()[2])
    assert width < 7500
    assert "TITLE BLOCK" not in svg
    assert "vector-effect" not in svg
    assert "BATHROOM" in svg


def test_arcs_render_as_open_geometry(tmp_path):
    path = tmp_path / "wall_plan.dxf"
    _build_wall_plan(path)

    svg = render_svg(import_dxf(path))

    assert '<circle class="bg door-line"' not in svg
    assert '<polyline class="bg door-line"' in svg
    assert 'class="bg wall-fill"' in svg
