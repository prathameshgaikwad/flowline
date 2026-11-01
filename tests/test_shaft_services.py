from core.consolidated import (
    nearest_water_source,
    stacks_for_building,
    water_sources_for_building,
)
from core.fixtures import make_fixture
from core.geometry import Point
from core.models import (
    Building,
    Design,
    FixtureType,
    Room,
    RoomPlan,
    Shaft,
    ShaftService,
    Stack,
)
from core.plumbing import build_plumbing
from core.rules.engine import load_profile


def _room():
    return Room(
        id="R-01",
        name="BATHROOM",
        boundary=[
            Point(x=0, y=0),
            Point(x=4000, y=0),
            Point(x=4000, y=3000),
            Point(x=0, y=3000),
        ],
    )


def test_only_drain_shafts_become_stacks_and_water_shafts_become_sources():
    building = Building(
        rooms=[_room()],
        shafts=[
            Shaft(
                id="S1",
                position=Point(x=1000, y=1000),
                services=[ShaftService.DRAIN, ShaftService.VENT],
            ),
            Shaft(
                id="S2",
                position=Point(x=3000, y=1000),
                services=[ShaftService.WATER],
            ),
        ],
    )

    stacks = stacks_for_building(building)
    sources = water_sources_for_building(building)

    assert len(stacks) == 1
    assert stacks[0].position == Point(x=1000, y=1000)
    assert stacks[0].shaft_id == "S1"
    assert len(sources) == 1
    assert sources[0].position == Point(x=3000, y=1000)
    assert sources[0].shaft_id == "S2"
    assert nearest_water_source(building.rooms[0], sources) == sources[0]


def test_combined_shaft_supplies_both_stack_and_water_source():
    building = Building(
        rooms=[_room()],
        shafts=[
            Shaft(
                id="S1",
                position=Point(x=1000, y=1000),
                services=[
                    ShaftService.DRAIN,
                    ShaftService.WATER,
                    ShaftService.VENT,
                ],
            )
        ],
    )

    stacks = stacks_for_building(building)
    sources = water_sources_for_building(building)

    assert len(stacks) == 1
    assert len(sources) == 1
    assert stacks[0].shaft_id == "S1"
    assert sources[0].shaft_id == "S1"


def test_vent_and_water_ports_stay_inside_their_shaft():
    shaft = Shaft(
        id="S1",
        position=Point(x=3500, y=300),
        width_mm=600,
        depth_mm=600,
        services=[
            ShaftService.DRAIN,
            ShaftService.WATER,
            ShaftService.VENT,
        ],
    )
    building = Building(rooms=[_room()], shafts=[shaft])
    stack = Stack(id="S1", position=shaft.position, shaft_id="S1")
    design = Design(
        room_id="R-01",
        profile_id="india_nbc_2016",
        room_plans=[
            RoomPlan(
                room_id="R-01",
                fixture_types=[FixtureType.WC],
                stack_id="S1",
                water_source_id="WS1",
            )
        ],
        fixtures=[
            make_fixture(
                "WC-01",
                FixtureType.WC,
                Point(x=1200, y=300),
                room_id="R-01",
            )
        ],
        stack=stack,
        stacks=[stack],
    )

    build_plumbing(building, design, load_profile("india_nbc_2016"))

    assert design.vent_stacks
    assert all(shaft.bbox.contains(item.position) for item in design.vent_stacks)
    assert all(item.shaft_id == "S1" for item in design.vent_stacks)
    assert design.water_source is not None
    assert shaft.bbox.contains(design.water_source.position)
    assert design.water_source.shaft_id == "S1"
