import ezdxf
import pytest

from core.dxf_import import import_dxf
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
