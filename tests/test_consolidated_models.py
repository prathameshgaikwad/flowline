from core.consolidated import nearest_stack, normalize_design, stacks_for_building
from core.geometry import Point
from core.models import (
    Building,
    Design,
    Fixture,
    FixtureType,
    Pipe,
    Room,
    RoomPlan,
    Shaft,
    Stack,
    System,
    VentStack,
)


def _stack(stack_id="S1", x=2200, y=300):
    return Stack(id=stack_id, position=Point(x=x, y=y))


def _fixture(fixture_id, room_id, fixture_type=FixtureType.WC, x=500):
    return Fixture(
        id=fixture_id,
        type=fixture_type,
        position=Point(x=x, y=350),
        room_id=room_id,
    )


def test_design_aggregates_room_plans_and_services():
    design = Design(
        room_id="R-01",
        profile_id="india_nbc_2016",
        room_plans=[
            RoomPlan(
                room_id="R-01",
                fixture_types=[FixtureType.WC, FixtureType.BASIN],
                layout_id="C-01",
                stack_id="S1",
            ),
            RoomPlan(
                room_id="R-02",
                fixture_types=[FixtureType.KITCHEN_SINK],
                layout_id="C-02",
                stack_id="S2",
            ),
        ],
        stacks=[_stack("S1"), _stack("S2", x=4400, y=300)],
        vent_stacks=[
            VentStack(id="VS1", stack_id="S1", position=Point(x=2500, y=300)),
            VentStack(id="VS2", stack_id="S2", position=Point(x=4700, y=300)),
        ],
        stack=_stack("S1"),
        fixtures=[
            _fixture("WC-01", "R-01"),
            _fixture("SINK-01", "R-02", FixtureType.KITCHEN_SINK, x=4400),
        ],
        pipes=[
            Pipe(
                id="D-01",
                system=System.SOIL,
                diameter_mm=100,
                points=[Point(x=500, y=350), Point(x=2200, y=300)],
                from_node="WC-01",
                to_node="S1",
                room_id="R-01",
            ),
            Pipe(
                id="D-02",
                system=System.WASTE,
                diameter_mm=50,
                points=[Point(x=4400, y=350), Point(x=4400, y=300)],
                from_node="SINK-01",
                to_node="S2",
                room_id="R-02",
            ),
        ],
    )

    assert design.room_ids == ["R-01", "R-02"]
    assert [item.id for item in design.fixtures_for_room("R-01")] == ["WC-01"]
    assert [item.id for item in design.fixtures_for_room("R-02")] == ["SINK-01"]
    assert [item.id for item in design.pipes_for_room("R-02")] == ["D-02"]
    assert design.stack_for_room("R-02").id == "S2"
    assert design.vent_stack_for_room("R-02").id == "VS2"
    assert design.reaches_stack("WC-01")
    assert design.reaches_stack("SINK-01")
    assert not design.reaches_stack("UNKNOWN")


def test_legacy_design_normalizes_to_one_room_plan():
    design = Design(
        room_id="R-01",
        profile_id="india_nbc_2016",
        layout_id="C-01",
        stack=_stack(),
        vent_stack=VentStack(position=Point(x=2500, y=300)),
        fixtures=[_fixture("WC-01", None)],
        pipes=[
            Pipe(
                id="D-01",
                system=System.SOIL,
                diameter_mm=100,
                points=[Point(x=500, y=350), Point(x=2200, y=300)],
                from_node="WC-01",
                to_node="S1",
            )
        ],
    )

    normalized = normalize_design(design)

    assert normalized.room_ids == ["R-01"]
    assert normalized.room_plans[0].layout_id == "C-01"
    assert normalized.room_plans[0].fixture_types == [FixtureType.WC]
    assert [stack.id for stack in normalized.stacks] == ["S1"]
    assert normalized.fixtures[0].room_id == "R-01"
    assert normalized.pipes[0].room_id == "R-01"
    assert normalized.vent_stack_for_room("R-01").id == "VS1"
    assert normalize_design(normalized) == normalized


def test_assigns_nearest_detected_stack():
    rooms = [
        Room(
            id="R1",
            name="BATHROOM",
            boundary=[Point(x=0, y=0), Point(x=2000, y=0), Point(x=2000, y=2000), Point(x=0, y=2000)],
        ),
        Room(
            id="R2",
            name="KITCHEN",
            boundary=[Point(x=8000, y=0), Point(x=10000, y=0), Point(x=10000, y=2000), Point(x=8000, y=2000)],
        ),
    ]
    building = Building(
        id="B1",
        rooms=rooms,
        shafts=[
            Shaft(id="SH1", position=Point(x=2200, y=1000)),
            Shaft(id="SH2", position=Point(x=7800, y=1000)),
        ],
    )

    stacks = stacks_for_building(building)

    assert [stack.id for stack in stacks] == ["S1", "S2"]
    assert nearest_stack(rooms[0], stacks).id == "S1"
    assert nearest_stack(rooms[1], stacks).id == "S2"
