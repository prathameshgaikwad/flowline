from core.fixes import apply_fix
from core.layout import generate_layouts
from core.models import Fix, FixtureType, Room
from core.plumbing import build_plumbing
from core.router import route_design
from core.rules.engine import load_profile, summarize, validate_design
from tests.test_consolidated_plumbing import _two_room_design


def test_validation_is_scoped_by_room():
    building, design = _two_room_design()
    profile = load_profile("india_nbc_2016")
    route_design(building, design, profile)
    build_plumbing(building, design, profile)

    results = validate_design(building, design, profile)

    assert summarize(results)["ERROR"] == 0
    assert {item.affected.get("room_id") for item in results} >= {"R1", "R2"}
    assert any(
        item.affected.get("pipe_id") and item.affected.get("room_id") == "R2"
        for item in results
    )
    loads = {
        item.affected["stack_id"]: item.measured
        for item in results
        if item.rule_id == "STACK_FIXTURE_LOAD"
    }
    assert set(loads) == {"S1", "S2"}
    assert all(value > 0 for value in loads.values())


def test_candidate_fix_changes_only_its_room():
    building, design = _two_room_design()
    profile = load_profile("india_nbc_2016")
    bathroom_candidates = generate_layouts(
        building,
        "R1",
        [design.room_plans[0].fixture_types[0]],
        design.stacks[0].position,
    )
    assert len(bathroom_candidates) >= 2
    original_bathroom = [
        (fixture.id, fixture.position.x, fixture.position.y)
        for fixture in design.fixtures_for_room("R1")
    ]
    original_kitchen = [
        (fixture.id, fixture.position.x, fixture.position.y)
        for fixture in design.fixtures_for_room("R2")
    ]
    alternate = next(
        candidate
        for candidate in bathroom_candidates
        if candidate.id != design.room_plan("R1").layout_id
    )

    updated = apply_fix(
        building,
        design,
        Fix(
            id=f"switch:R1:{alternate.id}",
            kind="SELECT_CANDIDATE",
            description="Try the alternate bathroom layout.",
            affected={"room_id": "R1", "layout_id": design.room_plan("R1").layout_id},
            params={"room_id": "R1", "candidate_id": alternate.id},
        ),
        profile,
        candidates_by_room={"R1": bathroom_candidates},
    )

    updated_kitchen = [
        (fixture.id, fixture.position.x, fixture.position.y)
        for fixture in updated.fixtures_for_room("R2")
    ]
    assert updated_kitchen == original_kitchen
    assert updated.room_plan("R1").layout_id == alternate.id
    assert updated.room_plan("R2").layout_id == "C-01"
    assert [
        (fixture.id, fixture.position.x, fixture.position.y)
        for fixture in updated.fixtures_for_room("R1")
    ] != original_bathroom


def test_small_balcony_and_powder_room_use_role_appropriate_minimums():
    from core.fixtures import make_fixture
    from core.geometry import Point
    from core.models import Building, Design, RoomPlan, Stack

    balcony = Room(
        id="R-BAL",
        name="BALCONY",
        boundary=[Point(x=0, y=0), Point(x=1200, y=0), Point(x=1200, y=1250), Point(x=0, y=1250)],
    )
    powder = Room(
        id="R-PWD",
        name="POWDER ROOM",
        boundary=[Point(x=2000, y=0), Point(x=3500, y=0), Point(x=3500, y=1500), Point(x=2000, y=1500)],
    )
    stacks = [Stack(id="S1", position=Point(x=1400, y=600))]
    design = Design(
        room_id=balcony.id,
        profile_id="india_nbc_2016",
        room_plans=[
            RoomPlan(room_id=balcony.id, fixture_types=[FixtureType.FLOOR_DRAIN], layout_id="C-01", stack_id="S1"),
            RoomPlan(room_id=powder.id, fixture_types=[FixtureType.WC, FixtureType.BASIN], layout_id="C-01", stack_id="S1"),
        ],
        stacks=stacks,
        stack=stacks[0],
        fixtures=[
            make_fixture("FD-BAL", FixtureType.FLOOR_DRAIN, Point(x=600, y=600), room_id=balcony.id),
            make_fixture("WC-PWD", FixtureType.WC, Point(x=2300, y=350), room_id=powder.id),
            make_fixture("BASIN-PWD", FixtureType.BASIN, Point(x=3000, y=350), room_id=powder.id),
        ],
    )
    building = Building(id="B1", rooms=[balcony, powder], shafts=[])

    results = validate_design(building, design, "india_nbc_2016")
    minimums = [
        result for result in results
        if result.rule_id in {"ROOM_MIN_AREA", "ROOM_MIN_WIDTH"} and result.severity != "PASS"
    ]

    assert minimums == []


def test_doors_are_scoped_to_their_room():
    from core.geometry import Point
    from core.models import Door

    building, design = _two_room_design()
    building.doors = [Door(id="D1", position=Point(x=1000, y=0), width_mm=750)]

    results = validate_design(building, design, "india_nbc_2016")

    door_widths = [item for item in results if item.rule_id == "DOOR_WIDTH"]
    assert len(door_widths) == 1
    assert door_widths[0].affected["room_id"] == "R1"
