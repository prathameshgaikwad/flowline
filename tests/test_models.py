import pytest

from core.geometry import Point
from core.models import Building, Design, Fixture, FixtureType, Room, Stack, System


def make_room():
    return Room(
        id="R1",
        name="Bathroom",
        boundary=[
            Point(x=0, y=0),
            Point(x=2400, y=0),
            Point(x=2400, y=1800),
            Point(x=0, y=1800),
        ],
    )


def test_room_area_bbox_and_containment():
    room = make_room()
    assert room.area_m2 == pytest.approx(4.32)
    assert room.bbox.width == 2400
    assert room.bbox.height == 1800
    assert room.contains(Point(x=1200, y=900))
    assert not room.contains(Point(x=3000, y=900))


def test_building_room_lookup():
    building = Building(id="B1", rooms=[make_room()])
    assert building.room("R1").name == "Bathroom"
    with pytest.raises(KeyError):
        building.room("missing")


def test_fixture_bbox_and_drain_point():
    fixture = Fixture(
        id="WC-01",
        type=FixtureType.WC,
        position=Point(x=500, y=350),
        width_mm=380,
        depth_mm=700,
        room_id="R1",
    )
    box = fixture.bbox
    assert box.minx == pytest.approx(310)
    assert box.maxx == pytest.approx(690)
    drain = fixture.drain_point(Point(x=2000, y=350))
    assert drain.x > fixture.position.x
    assert drain.y == pytest.approx(fixture.position.y)


def test_design_defaults():
    design = Design(room_id="R1", profile_id="india_nbc_2016", stack=Stack(id="S1", position=Point(x=2200, y=300)))
    assert design.fixtures == []
    assert design.pipes == []
    assert design.stack.id == "S1"
    assert System.SOIL.value == "SOIL"
