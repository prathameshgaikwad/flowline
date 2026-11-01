from pathlib import Path

from agent.tools import TOOLS, AgentSession, RoomChoice
from core.dxf_import import import_dxf
from core.models import Stack
from core.plumbing_zones import default_fixtures
from core.sample_plan import build_apartment


def _consolidated_session(tmp_path: Path) -> AgentSession:
    path = tmp_path / "apartment.dxf"
    build_apartment(path)
    building = import_dxf(path)
    bathroom = next(room for room in building.rooms if room.name == "BATHROOM")
    kitchen = next(room for room in building.rooms if room.name == "KITCHEN")
    stack = Stack(id="S1", position=building.shafts[0].position)
    return AgentSession(
        building=building,
        source_path=path,
        out_dir=tmp_path / "out",
        room_id=bathroom.id,
        fixture_types=default_fixtures(bathroom.plumbing_role),
        stack=stack,
        stacks={"S1": stack},
        room_choices=[
            RoomChoice(
                bathroom.id,
                default_fixtures(bathroom.plumbing_role),
                stack.id,
            ),
            RoomChoice(kitchen.id, default_fixtures(kitchen.plumbing_role), stack.id),
        ],
        profile_id="india_nbc_2016",
    )


def test_plan_room_layouts_builds_one_design_for_all_rooms(tmp_path):
    session = _consolidated_session(tmp_path)

    result = TOOLS["plan_room_layouts"].run({}, session)

    assert result["failures"] == []
    assert len(result["rooms"]) == 2
    assert session.design is not None
    assert session.design.room_ids == [choice.room_id for choice in session.room_choices]
    assert all(plan.layout_id for plan in session.design.room_plans)
    assert set(session.candidates_by_room) == set(session.design.room_ids)
    assert set(session.selected_candidates) == set(session.design.room_ids)
    assert {fixture.room_id for fixture in session.design.fixtures} == set(
        session.design.room_ids
    )
    assert any(
        decision["kind"] == "layout_selected" and decision.get("room_id")
        for decision in session.decisions
    )


def test_layout_failure_is_isolated_to_one_room(tmp_path):
    session = _consolidated_session(tmp_path)
    failed_room = next(
        room for room in session.building.rooms if room.name == "KITCHEN"
    )
    failed_room.closed = False

    result = TOOLS["plan_room_layouts"].run({}, session)

    assert [item["room_id"] for item in result["failures"]] == [failed_room.id]
    assert session.design is not None
    assert failed_room.id not in session.design.room_ids
    assert len(session.design.room_ids) == 1


def test_select_layout_can_change_one_room_without_touching_another(tmp_path):
    session = _consolidated_session(tmp_path)
    TOOLS["plan_room_layouts"].run({}, session)
    bathroom_id, kitchen_id = session.design.room_ids
    bathroom_count = len(session.design.fixtures_for_room(bathroom_id))

    options = TOOLS["list_layout_options"].run({"room_id": kitchen_id}, session)
    candidate_id = options["candidates"][0]["id"]
    TOOLS["select_layout"].run(
        {
            "room_id": kitchen_id,
            "candidate_id": candidate_id,
            "rationale": "Kitchen sink on the stack wall.",
        },
        session,
    )

    assert len(session.design.fixtures_for_room(bathroom_id)) == bathroom_count
    assert len(session.design.fixtures_for_room(kitchen_id)) == 1
    assert session.design.room_plan(kitchen_id).layout_id == candidate_id


def test_consolidated_routing_and_services_cover_both_rooms(tmp_path):
    session = _consolidated_session(tmp_path)
    TOOLS["plan_room_layouts"].run({}, session)
    routed = TOOLS["route_drainage"].run({}, session)
    services = TOOLS["route_services"].run({}, session)

    assert routed["count"] == 4
    assert {pipe.room_id for pipe in session.design.pipes} == set(
        session.design.room_ids
    )
    assert services["vent_pipes"]
    assert {pipe.room_id for pipe in session.design.vent_pipes} == set(
        session.design.room_ids
    )


def test_plan_room_layouts_requires_a_room_selection(tmp_path):
    path = tmp_path / "apartment.dxf"
    build_apartment(path)
    building = import_dxf(path)
    session = AgentSession(
        building=building,
        source_path=path,
        out_dir=tmp_path / "out",
        stack=Stack(id="S1", position=building.shafts[0].position),
    )

    result = TOOLS["plan_room_layouts"].run({}, session)

    assert result["rooms"] == []
    assert result["failures"] == [{"room_id": "", "error": "No rooms selected."}]


def test_fixture_ids_are_unique_across_identical_rooms(tmp_path):
    from core.geometry import Point
    from core.models import Building, FixtureType, Room, Shaft, Stack

    rooms = [
        Room(
            id="R-A",
            name="BATHROOM",
            boundary=[Point(x=0, y=0), Point(x=3000, y=0), Point(x=3000, y=2400), Point(x=0, y=2400)],
        ),
        Room(
            id="R-B",
            name="BATHROOM",
            boundary=[Point(x=4000, y=0), Point(x=7000, y=0), Point(x=7000, y=2400), Point(x=4000, y=2400)],
        ),
    ]
    building = Building(
        id="B1",
        rooms=rooms,
        shafts=[Shaft(id="SH1", position=Point(x=3200, y=1200))],
    )
    stack = Stack(id="S1", position=building.shafts[0].position)
    source = tmp_path / "two_baths.dxf"
    source.write_text("", encoding="utf-8")
    session = AgentSession(
        building=building,
        source_path=source,
        out_dir=tmp_path / "out",
        room_id="R-A",
        fixture_types=[FixtureType.WC, FixtureType.BASIN, FixtureType.SHOWER],
        stack=stack,
        stacks={"S1": stack},
        room_choices=[
            RoomChoice("R-A", [FixtureType.WC, FixtureType.BASIN, FixtureType.SHOWER], "S1"),
            RoomChoice("R-B", [FixtureType.WC, FixtureType.BASIN, FixtureType.SHOWER], "S1"),
        ],
    )

    TOOLS["plan_room_layouts"].run({}, session)

    ids = [fixture.id for fixture in session.design.fixtures]
    assert len(ids) == len(set(ids))
    assert all(fixture.room_id for fixture in session.design.fixtures)
