import ezdxf

from core.dxf_import import import_dxf


def _new_doc():
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    return doc


def _add_bathroom(msp):
    msp.add_lwpolyline(
        [(0, 0), (2400, 0), (2400, 1800), (0, 1800)],
        close=True,
        dxfattribs={"layer": "A-ROOM"},
    )
    msp.add_text(
        "BATHROOM", dxfattribs={"layer": "A-TEXT", "height": 150}
    ).set_placement((1200, 900))


def _add_hatch(msp, layer, points):
    hatch = msp.add_hatch(dxfattribs={"layer": layer})
    hatch.paths.add_polyline_path(points, is_closed=True)
    return hatch


def test_explicit_shaft_layer_creates_combined_service_shaft(tmp_path):
    path = tmp_path / "explicit_shaft.dxf"
    doc = _new_doc()
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(1000, 1000), (1600, 1000), (1600, 1600), (1000, 1600)],
        close=True,
        dxfattribs={"layer": "A-SHAFT"},
    )
    doc.saveas(path)

    building = import_dxf(path)

    assert len(building.shafts) == 1
    shaft = building.shafts[0]
    assert {service.value for service in shaft.services} == {"DRAIN", "WATER", "VENT"}
    assert shaft.source == "explicit"
    assert shaft.width_mm == 600
    assert shaft.depth_mm == 600


def test_inferred_solid_hatch_near_wet_room_creates_shaft(tmp_path):
    path = tmp_path / "inferred_shaft.dxf"
    doc = _new_doc()
    msp = doc.modelspace()
    _add_bathroom(msp)
    _add_hatch(
        msp,
        "Y01 Hatch - Working+Presentation",
        [(2500, 0), (2750, 0), (2750, 750), (2500, 750)],
    )
    doc.saveas(path)

    building = import_dxf(path)

    assert len(building.shafts) == 1
    shaft = building.shafts[0]
    assert shaft.source == "inferred_hatch"
    assert round(shaft.width_mm) == 250
    assert round(shaft.depth_mm) == 750
    assert {service.value for service in shaft.services} == {"DRAIN", "WATER", "VENT"}


def test_large_floor_hatch_is_not_a_shaft(tmp_path):
    path = tmp_path / "floor_hatch.dxf"
    doc = _new_doc()
    msp = doc.modelspace()
    _add_bathroom(msp)
    _add_hatch(
        msp,
        "Y01 Hatch - Working+Presentation",
        [(0, 0), (9000, 0), (9000, 7000), (0, 7000)],
    )
    doc.saveas(path)

    building = import_dxf(path)

    assert building.shafts == []


def test_column_hatch_is_not_a_shaft(tmp_path):
    path = tmp_path / "column_hatch.dxf"
    doc = _new_doc()
    msp = doc.modelspace()
    _add_bathroom(msp)
    _add_hatch(
        msp,
        "B01 Columns",
        [(2500, 0), (2750, 0), (2750, 750), (2500, 750)],
    )
    doc.saveas(path)

    building = import_dxf(path)

    assert building.shafts == []


def test_shaft_label_selects_water_service(tmp_path):
    path = tmp_path / "water_shaft.dxf"
    doc = _new_doc()
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(1000, 1000), (1600, 1000), (1600, 1600), (1000, 1600)],
        close=True,
        dxfattribs={"layer": "A-SHAFT"},
    )
    msp.add_text(
        "WATER SHAFT", dxfattribs={"layer": "A-TEXT", "height": 120}
    ).set_placement((1300, 1300))
    doc.saveas(path)

    building = import_dxf(path)

    assert len(building.shafts) == 1
    assert {service.value for service in building.shafts[0].services} == {"WATER"}
    assert building.shafts[0].name == "WATER SHAFT"
