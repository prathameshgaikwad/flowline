
from core.fixtures import make_fixture
from core.geometry import Point
from core.models import (
    Building,
    Design,
    FixtureType,
    Room,
    RoomPlan,
    Stack,
)
from core.plumbing import build_plumbing
from core.router import route_design
from core.rules.engine import load_profile


def _two_room_design():
    bathroom = Room(
        id="R1",
        name="BATHROOM",
        boundary=[
            Point(x=0, y=0),
            Point(x=3000, y=0),
            Point(x=3000, y=2400),
            Point(x=0, y=2400),
        ],
    )
    kitchen = Room(
        id="R2",
        name="KITCHEN",
        boundary=[
            Point(x=5000, y=0),
            Point(x=8000, y=0),
            Point(x=8000, y=2400),
            Point(x=5000, y=2400),
        ],
    )
    stacks = [
        Stack(id="S1", position=Point(x=3200, y=1200)),
        Stack(id="S2", position=Point(x=7800, y=1200)),
    ]
    design = Design(
        id="DESIGN-CONSOLIDATED",
        room_id="R1",
        profile_id="india_nbc_2016",
        room_plans=[
            RoomPlan(
                room_id="R1",
                fixture_types=[FixtureType.WC],
                layout_id="C-01",
                stack_id="S1",
            ),
            RoomPlan(
                room_id="R2",
                fixture_types=[FixtureType.KITCHEN_SINK],
                layout_id="C-01",
                stack_id="S2",
            ),
        ],
        stacks=stacks,
        stack=stacks[0],
        fixtures=[
            make_fixture("WC-01", FixtureType.WC, Point(x=500, y=350), room_id="R1"),
            make_fixture(
                "SINK-01",
                FixtureType.KITCHEN_SINK,
                Point(x=5500, y=350),
                room_id="R2",
            ),
        ],
    )
    return Building(id="B1", rooms=[bathroom, kitchen], shafts=[]), design


def test_routes_each_room_to_its_assigned_stack():
    building, design = _two_room_design()
    pipes = route_design(building, design, load_profile("india_nbc_2016"))

    assert len(pipes) == 2
    assert {(pipe.room_id, pipe.to_node) for pipe in pipes} == {
        ("R1", "S1"),
        ("R2", "S2"),
    }
    assert all(pipe.points[-1] == design.stack_for_room(pipe.room_id).position for pipe in pipes)
    assert all(pipe.slope and pipe.slope > 0 for pipe in pipes)


def test_builds_services_for_every_room_and_stack():
    building, design = _two_room_design()
    route_design(building, design, load_profile("india_nbc_2016"))
    build_plumbing(building, design, load_profile("india_nbc_2016"))

    assert [stack.stack_id for stack in design.vent_stacks] == ["S1", "S2"]
    assert design.water_source is not None
    assert {pipe.room_id for pipe in design.vent_pipes} == {"R1", "R2"}
    assert {pipe.room_id for pipe in design.supply_pipes} == {"R1", "R2"}
    assert {pipe.to_node for pipe in design.vent_pipes} == {"VS1", "VS2"}
    assert all(
        item.room_id in {"R1", "R2"}
        for item in design.plumbing_items
        if item.room_id is not None
    )
    cleanouts = [item for item in design.plumbing_items if item.type.value == "CLEANOUT"]
    vents = [
        item
        for item in design.plumbing_items
        if item.type.value == "VENT_TERMINATION"
    ]
    assert len(cleanouts) == 2
    assert len(vents) == 2


def test_route_failure_preserves_successful_room_pipes():
    building, design = _two_room_design()
    design.room_plans[0].stack_id = "S2"
    design.room_plans[1].stack_id = "S1"
    design.stacks[0].position = Point(x=500_000, y=500_000)

    pipes = route_design(building, design, load_profile("india_nbc_2016"))

    assert design.room_ids == ["R1", "R2"]
    assert [pipe.room_id for pipe in pipes] == ["R1"]
    assert design.route_failures
    assert "R2" in design.route_failures[0]
