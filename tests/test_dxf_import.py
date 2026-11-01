import ezdxf
import pytest

from core.dxf_import import import_dxf
from core.models import FixtureType
from core.plumbing_zones import PlumbingRole
from core.sample_plan import build_apartment, build_tight_bathroom


def test_imports_apartment_rooms_door_and_shaft(tmp_path):
    path = tmp_path / "apartment.dxf"
    build_apartment(path)

    building = import_dxf(path)

    assert len(building.rooms) >= 3
    bath = next(room for room in building.rooms if "bath" in (room.name or "").lower())
    assert bath.area_m2 == pytest.approx(4.32, rel=0.01)
    assert len(building.doors) >= 1
    assert len(building.shafts) >= 1
    assert building.units == "mm"
    assert building.rooms[0].closed


def test_imports_tight_bathroom(tmp_path):
    path = tmp_path / "tight.dxf"
    build_tight_bathroom(path)
    building = import_dxf(path)
    assert len(building.rooms) == 1
    assert building.rooms[0].area_m2 == pytest.approx(1.8, rel=0.01)


def test_metre_drawing_is_converted_to_mm(tmp_path):
    path = tmp_path / "metres.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (2.4, 0), (2.4, 1.8), (0, 1.8)], close=True, dxfattribs={"layer": "A-ROOM"}
    )
    msp.add_text("BATHROOM", dxfattribs={"layer": "A-TEXT", "height": 0.15}).set_placement(
        (1.2, 0.9)
    )
    doc.saveas(path)

    building = import_dxf(path)

    assert building.source_scale == pytest.approx(1000.0)
    assert building.rooms[0].area_m2 == pytest.approx(4.32, rel=0.01)


def test_unitless_drawing_warns(tmp_path):
    path = tmp_path / "unitless.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 0
    doc.modelspace().add_lwpolyline(
        [(0, 0), (2400, 0), (2400, 1800), (0, 1800)],
        close=True,
        dxfattribs={"layer": "A-ROOM"},
    )
    doc.saveas(path)

    building = import_dxf(path)
    assert any("millimetres" in warning for warning in building.warnings)


def test_open_polyline_is_not_a_room(tmp_path):
    path = tmp_path / "open.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    doc.modelspace().add_lwpolyline(
        [(0, 0), (2400, 0), (2400, 1800), (0, 1800)],
        close=False,
        dxfattribs={"layer": "A-ROOM"},
    )
    doc.saveas(path)

    building = import_dxf(path)
    assert building.rooms == []
    assert any("No closed room boundaries" in warning for warning in building.warnings)


def test_mirrored_block_geometry_is_read_in_wcs(tmp_path):
    path = tmp_path / "mirrored.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    block = doc.blocks.new("MIRRORED_ROOM")
    block.add_lwpolyline(
        [(0, 0), (2400, 0), (2400, 1800), (0, 1800)],
        close=True,
        dxfattribs={"layer": "A-ROOM"},
    )
    doc.modelspace().add_blockref(
        "MIRRORED_ROOM",
        (-5000, 0),
        dxfattribs={"xscale": -1, "yscale": 1},
    )
    doc.saveas(path)

    building = import_dxf(path)

    assert len(building.rooms) == 1
    xs = [point.x for point in building.rooms[0].boundary]
    assert max(xs) < 0
    assert building.rooms[0].bbox.width == pytest.approx(2400, rel=0.01)
    assert building.rooms[0].area_m2 == pytest.approx(4.32, rel=0.01)


def test_wall_patch_hatch_splits_rooms(tmp_path):
    path = tmp_path / "hatch_partition.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()

    def wall(x1, y1, x2, y2):
        msp.add_lwpolyline(
            [(x1, y1), (x2, y1), (x2, y2), (x1, y2)],
            close=True,
            dxfattribs={"layer": "WALLS"},
        )

    wall(0, 0, 6000, 200)
    wall(0, 2800, 6000, 3000)
    wall(0, 200, 200, 2800)
    wall(5800, 200, 6000, 2800)

    hatch = msp.add_hatch(dxfattribs={"layer": "X01 Wall Patches"})
    hatch.paths.add_polyline_path(
        [(2900, 200), (3100, 200), (3100, 2800), (2900, 2800)],
        is_closed=True,
    )
    doc.saveas(path)

    building = import_dxf(path)

    assert len(building.rooms) == 2
    areas = sorted(round(room.area_m2, 1) for room in building.rooms)
    assert areas == [7.8, 7.8]


def test_sanitaryware_layer_marks_unnamed_room_as_powder(tmp_path):
    path = tmp_path / "sanitaryware.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (2400, 0), (2400, 1800), (0, 1800)],
        close=True,
        dxfattribs={"layer": "A-ROOM"},
    )
    block = doc.blocks.new("A$C12345")
    block.add_lwpolyline(
        [(0, 0), (600, 0), (600, 400), (0, 400)],
        close=True,
    )
    msp.add_blockref(
        "A$C12345",
        (1200, 900),
        dxfattribs={"layer": "M03 Sanitaryware"},
    )
    doc.saveas(path)

    building = import_dxf(path)

    assert len(building.rooms) == 1
    room = building.rooms[0]
    assert room.plumbing_role == PlumbingRole.POWDER
    assert room.default_fixtures == [FixtureType.WC, FixtureType.BASIN]


def test_door_block_with_children_is_detected_once(tmp_path):
    path = tmp_path / "door_block.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    block = doc.blocks.new("DOOR900")
    block.add_line((0, 0), (900, 0))
    block.add_arc((0, 0), 900, 0, 90)
    doc.modelspace().add_blockref(
        "DOOR900",
        (1200, 0),
        dxfattribs={"layer": "A-DOOR"},
    )
    doc.saveas(path)

    building = import_dxf(path)

    assert len(building.doors) == 1
    assert building.doors[0].position.x == pytest.approx(1200, abs=1)


def test_wall_hatch_fill_is_not_a_room(tmp_path):
    path = tmp_path / "wall_fill.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    hatch = doc.modelspace().add_hatch(
        dxfattribs={"layer": "X01 Wall Patches"}
    )
    hatch.paths.add_polyline_path(
        [(0, 0), (6000, 0), (6000, 200), (0, 200)],
        is_closed=True,
    )
    doc.saveas(path)

    building = import_dxf(path)

    assert building.rooms == []


def test_floor_hatch_adds_missing_room_without_guessing_role(tmp_path):
    path = tmp_path / "floor_hatch.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (2400, 0), (2400, 1800), (0, 1800)],
        close=True,
        dxfattribs={"layer": "A-ROOM"},
    )
    hatch = msp.add_hatch(
        dxfattribs={"layer": "Y01 Hatch - Working+Presentation"}
    )
    hatch.paths.add_polyline_path(
        [(3000, 0), (5400, 0), (5400, 1800), (3000, 1800)],
        is_closed=True,
    )
    block = doc.blocks.new("A$C67890")
    block.add_lwpolyline(
        [(0, 0), (600, 0), (600, 400), (0, 400)],
        close=True,
    )
    msp.add_blockref(
        "A$C67890",
        (4200, 900),
        dxfattribs={"layer": "M03 Sanitaryware"},
    )
    doc.saveas(path)

    building = import_dxf(path)

    assert len(building.rooms) == 2
    added = next(room for room in building.rooms if room.area_m2 == pytest.approx(4.32, rel=0.01))
    assert added.name is None
    assert added.plumbing_role == PlumbingRole.NONE


def test_unsupported_entities_do_not_crash(tmp_path):
    path = tmp_path / "unsupported.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    msp.add_spline([(0, 0, 0), (100, 100, 0), (200, 0, 0)])
    msp.add_hatch(color=2)
    doc.saveas(path)

    building = import_dxf(path)
    assert building.rooms == []
