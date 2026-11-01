import ezdxf
import pytest

from core.dxf_import import import_dxf
from core.geometry import Point
from core.models import FixtureType, Room
from core.plumbing_zones import PlumbingRole, classify_room, default_fixtures

BOUNDARY = [Point(x=0, y=0), Point(x=1, y=0), Point(x=0, y=1)]


@pytest.mark.parametrize(
    ("name", "role"),
    [
        ("BATHROOM", PlumbingRole.BATHROOM),
        ("COMMON BATHROOM", PlumbingRole.BATHROOM),
        ("WASHROOM", PlumbingRole.BATHROOM),
        ("MASTER ENSUITE", PlumbingRole.BATHROOM),
        ("SHOWER ROOM", PlumbingRole.BATHROOM),
        ("TOILET", PlumbingRole.POWDER),
        ("POWDER ROOM", PlumbingRole.POWDER),
        ("KITCHEN", PlumbingRole.KITCHEN),
        ("KITCHENETTE", PlumbingRole.KITCHEN),
        ("PANTRY", PlumbingRole.KITCHEN),
        ("BALCONY", PlumbingRole.BALCONY),
        ("SERVICE BALCONY", PlumbingRole.BALCONY),
        ("UTILITY", PlumbingRole.UTILITY),
        ("LAUNDRY", PlumbingRole.UTILITY),
        ("WASH BASIN", PlumbingRole.WASH_AREA),
        ("WASH AREA", PlumbingRole.WASH_AREA),
        ("BEDROOM", PlumbingRole.NONE),
        ("LIVING ROOM", PlumbingRole.NONE),
        ("DINING", PlumbingRole.NONE),
        (None, PlumbingRole.NONE),
    ],
)
def test_classifies_room_labels(name, role):
    assert classify_room(name, []) == role


@pytest.mark.parametrize(
    ("hints", "role"),
    [
        ([FixtureType.WC], PlumbingRole.BATHROOM),
        ([FixtureType.SHOWER], PlumbingRole.BATHROOM),
        ([FixtureType.KITCHEN_SINK], PlumbingRole.KITCHEN),
        ([FixtureType.BASIN], PlumbingRole.WASH_AREA),
        ([FixtureType.FLOOR_DRAIN], PlumbingRole.BALCONY),
    ],
)
def test_classifies_fixture_hints(hints, role):
    assert classify_room(None, hints) == role


def test_default_fixtures_for_roles():
    assert default_fixtures(PlumbingRole.BATHROOM) == [
        FixtureType.WC,
        FixtureType.BASIN,
        FixtureType.SHOWER,
    ]
    assert default_fixtures(PlumbingRole.POWDER) == [
        FixtureType.WC,
        FixtureType.BASIN,
    ]
    assert default_fixtures(PlumbingRole.KITCHEN) == [FixtureType.KITCHEN_SINK]
    assert default_fixtures(PlumbingRole.BALCONY) == [FixtureType.FLOOR_DRAIN]
    assert default_fixtures(PlumbingRole.UTILITY) == [
        FixtureType.FLOOR_DRAIN,
        FixtureType.BASIN,
    ]
    assert default_fixtures(PlumbingRole.WASH_AREA) == [FixtureType.BASIN]
    assert default_fixtures(PlumbingRole.NONE) == []


def test_room_uses_plumbing_role_for_wet_area():
    bathroom = Room(
        id="R1",
        name="BATHROOM",
        boundary=BOUNDARY,
    )
    bedroom = Room(
        id="R2",
        name="BEDROOM",
        boundary=BOUNDARY,
    )

    assert bathroom.plumbing_role == PlumbingRole.BATHROOM
    assert bathroom.is_wet_area
    assert bedroom.plumbing_role == PlumbingRole.NONE
    assert not bedroom.is_wet_area


def test_imports_fixture_block_hint_for_unnamed_room(tmp_path):
    path = tmp_path / "hinted_room.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (2400, 0), (2400, 1800), (0, 1800)],
        close=True,
        dxfattribs={"layer": "A-ROOM"},
    )
    block = doc.blocks.new("KITCHEN_SINK_600")
    block.add_lwpolyline(
        [(0, 0), (600, 0), (600, 500), (0, 500)],
        close=True,
    )
    msp.add_blockref("KITCHEN_SINK_600", (1200, 900))
    doc.saveas(path)

    building = import_dxf(path)

    assert len(building.rooms) == 1
    room = building.rooms[0]
    assert room.name is None
    assert room.fixture_hints == [FixtureType.KITCHEN_SINK]
    assert room.plumbing_role == PlumbingRole.KITCHEN
    assert room.default_fixtures == [FixtureType.KITCHEN_SINK]


def test_existing_room_is_named_room_without_hints():
    room = Room(
        id="R1",
        name="BATHROOM",
        boundary=BOUNDARY,
    )
    assert room.fixture_hints == []
    assert room.default_fixtures == [
        FixtureType.WC,
        FixtureType.BASIN,
        FixtureType.SHOWER,
    ]


def test_keeps_unnamed_room_with_fixture_hint_next_to_labeled_room(tmp_path):
    path = tmp_path / "mixed_rooms.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (2400, 0), (2400, 1800), (0, 1800)],
        close=True,
        dxfattribs={"layer": "A-ROOM"},
    )
    msp.add_text("BATHROOM", dxfattribs={"layer": "A-TEXT", "height": 150}).set_placement((1200, 900))
    msp.add_lwpolyline(
        [(2600, 0), (5000, 0), (5000, 1800), (2600, 1800)],
        close=True,
        dxfattribs={"layer": "A-ROOM"},
    )
    block = doc.blocks.new("KITCHEN_SINK_600")
    block.add_lwpolyline([(0, 0), (600, 0), (600, 500), (0, 500)], close=True)
    msp.add_blockref("KITCHEN_SINK_600", (3800, 900))
    doc.saveas(path)

    building = import_dxf(path)

    assert len(building.rooms) == 2
    unnamed = next(room for room in building.rooms if room.name is None)
    assert unnamed.plumbing_role == PlumbingRole.KITCHEN
    assert unnamed.default_fixtures == [FixtureType.KITCHEN_SINK]
