import ezdxf

from core.dxf_import import import_dxf
from core.models import FixtureType


def _new_doc():
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    return doc


def _add_room(msp, label="BATHROOM"):
    msp.add_lwpolyline(
        [(0, 0), (2400, 0), (2400, 1800), (0, 1800)],
        close=True,
        dxfattribs={"layer": "A-ROOM"},
    )
    if label:
        msp.add_text(
            label, dxfattribs={"layer": "A-TEXT", "height": 150}
        ).set_placement((1200, 900))


def _add_fixture_block(doc, msp, name, width, depth, position=(1200, 900)):
    block = doc.blocks.new(name)
    block.add_lwpolyline(
        [
            (-width / 2, -depth / 2),
            (width / 2, -depth / 2),
            (width / 2, depth / 2),
            (-width / 2, depth / 2),
        ],
        close=True,
    )
    msp.add_blockref(
        name,
        position,
        dxfattribs={"layer": "M03 Sanitaryware"},
    )


def _fixtures(building):
    return building.detected_fixtures


def test_detects_generic_wc_from_block_size(tmp_path):
    path = tmp_path / "wc.dxf"
    doc = _new_doc()
    msp = doc.modelspace()
    _add_room(msp)
    _add_fixture_block(doc, msp, "A$C660E3542", 650, 550)
    doc.saveas(path)

    building = import_dxf(path)

    fixtures = _fixtures(building)
    assert len(fixtures) == 1
    assert fixtures[0].type == FixtureType.WC
    assert fixtures[0].room_id == "R-01"
    assert round(fixtures[0].width_mm) == 650
    assert round(fixtures[0].depth_mm) == 550


def test_detects_generic_basin_from_block_size(tmp_path):
    path = tmp_path / "basin.dxf"
    doc = _new_doc()
    msp = doc.modelspace()
    _add_room(msp)
    _add_fixture_block(doc, msp, "Cubica", 340, 528)
    doc.saveas(path)

    building = import_dxf(path)

    fixtures = _fixtures(building)
    assert len(fixtures) == 1
    assert fixtures[0].type == FixtureType.BASIN


def test_detects_floor_drain_and_shower_from_geometry(tmp_path):
    path = tmp_path / "wet_fixtures.dxf"
    doc = _new_doc()
    msp = doc.modelspace()
    _add_room(msp)
    _add_fixture_block(doc, msp, "A$C642549C4", 118, 118, (600, 300))
    _add_fixture_block(doc, msp, "A$C900", 900, 900, (1700, 900))
    doc.saveas(path)

    building = import_dxf(path)

    types = {fixture.type for fixture in _fixtures(building)}
    assert types == {FixtureType.FLOOR_DRAIN, FixtureType.SHOWER}


def test_ambiguous_sanitaryware_rect_is_not_given_a_fixture_type(tmp_path):
    path = tmp_path / "ambiguous.dxf"
    doc = _new_doc()
    msp = doc.modelspace()
    _add_room(msp, label=None)
    _add_fixture_block(doc, msp, "A$C12345", 600, 400)
    doc.saveas(path)

    building = import_dxf(path)

    assert _fixtures(building) == []
    assert building.rooms[0].has_sanitaryware is True
    assert building.rooms[0].default_fixtures == [
        FixtureType.WC,
        FixtureType.BASIN,
    ]


def test_nested_fixture_container_counts_leaf_fixtures_once(tmp_path):
    path = tmp_path / "nested.dxf"
    doc = _new_doc()
    msp = doc.modelspace()
    _add_room(msp)
    wc = doc.blocks.new("WC_BLOCK")
    wc.add_lwpolyline(
        [(-325, -275), (325, -275), (325, 275), (-325, 275)],
        close=True,
    )
    basin = doc.blocks.new("BASIN_BLOCK")
    basin.add_lwpolyline(
        [(-170, -264), (170, -264), (170, 264), (-170, 264)],
        close=True,
    )
    container = doc.blocks.new("BATHROOM_SET")
    container.add_blockref(
        "WC_BLOCK", (700, 900), dxfattribs={"layer": "M03 Sanitaryware"}
    )
    container.add_blockref(
        "BASIN_BLOCK", (1600, 900), dxfattribs={"layer": "M03 Sanitaryware"}
    )
    msp.add_blockref(
        "BATHROOM_SET",
        (0, 0),
        dxfattribs={"layer": "M03 Sanitaryware"},
    )
    doc.saveas(path)

    building = import_dxf(path)

    fixtures = _fixtures(building)
    assert len(fixtures) == 2
    assert {fixture.type for fixture in fixtures} == {
        FixtureType.WC,
        FixtureType.BASIN,
    }
    assert all(fixture.room_id == "R-01" for fixture in fixtures)


def test_detected_fixtures_replace_role_defaults(tmp_path):
    path = tmp_path / "defaults.dxf"
    doc = _new_doc()
    msp = doc.modelspace()
    _add_room(msp)
    _add_fixture_block(doc, msp, "A$C660E3542", 650, 550, (700, 900))
    _add_fixture_block(doc, msp, "Cubica", 340, 528, (1600, 900))
    doc.saveas(path)

    building = import_dxf(path)
    room = building.rooms[0]

    assert room.fixture_hints == [FixtureType.WC, FixtureType.BASIN]
    assert room.default_fixtures == [FixtureType.WC, FixtureType.BASIN]


def test_named_kitchen_sink_is_detected_in_kitchen(tmp_path):
    path = tmp_path / "kitchen.dxf"
    doc = _new_doc()
    msp = doc.modelspace()
    _add_room(msp, label="KITCHEN")
    _add_fixture_block(doc, msp, "Kitchen Sink", 450, 450)
    doc.saveas(path)

    building = import_dxf(path)

    fixtures = _fixtures(building)
    assert len(fixtures) == 1
    assert fixtures[0].type == FixtureType.KITCHEN_SINK
    assert building.rooms[0].fixture_hints == [FixtureType.KITCHEN_SINK]
