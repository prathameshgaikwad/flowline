import pytest

from core.dxf_import import import_dxf
from core.fixtures import make_fixture
from core.geometry import Point
from core.layout import generate_layouts
from core.models import Building, Design, FixtureType, Room, Stack, System
from core.router import route_design
from core.rules.engine import (
    available_profiles,
    load_profile,
    summarize,
    validate_design,
)
from core.sample_plan import build_apartment, build_tight_bathroom


def sample_design(tmp_path, profile_id="india_nbc_2016"):
    path = tmp_path / "apartment.dxf"
    build_apartment(path)
    building = import_dxf(path)
    room = next(room for room in building.rooms if "bath" in (room.name or "").lower())
    stack = Stack(id="S1", position=building.shafts[0].position)
    candidate = generate_layouts(
        building,
        room.id,
        [FixtureType.WC, FixtureType.BASIN, FixtureType.SHOWER],
        stack.position,
    )[0]
    design = Design(
        room_id=room.id,
        profile_id=profile_id,
        stack=stack,
        fixtures=candidate.fixtures,
        layout_id=candidate.id,
    )
    route_design(building, design, load_profile(profile_id))
    return building, design


def test_profiles_load():
    assert available_profiles() == ["india_nbc_2016", "us_ipc_2021"]
    india = load_profile("india_nbc_2016")
    us = load_profile("us_ipc_2021")
    assert india.pipe_for("WC").diameter_mm == 100
    assert us.pipe_for("WC").diameter_mm == 76
    assert india.stack.min_diameter_mm == 100
    assert us.vent.max_branch_mm_warning == 2400


def test_sample_india_design_has_no_errors(tmp_path):
    building, design = sample_design(tmp_path)
    results = validate_design(building, design, "india_nbc_2016")
    counts = summarize(results)
    assert counts["ERROR"] == 0
    assert counts["WARNING"] >= 1
    assert counts["PASS"] > 0
    assert all(result.source for result in results)


def test_sample_us_design_has_no_errors(tmp_path):
    building, design = sample_design(tmp_path, "us_ipc_2021")
    results = validate_design(building, design, "us_ipc_2021")
    assert summarize(results)["ERROR"] == 0


def test_tight_bathroom_flags_room_size(tmp_path):
    path = tmp_path / "tight.dxf"
    build_tight_bathroom(path)
    building = import_dxf(path)
    room = building.rooms[0]
    stack = Stack(id="S1", position=building.shafts[0].position)
    design = Design(
        room_id=room.id,
        profile_id="india_nbc_2016",
        stack=stack,
        fixtures=[
            make_fixture("WC-01", FixtureType.WC, Point(x=300, y=350), room_id=room.id),
            make_fixture("BASIN-01", FixtureType.BASIN, Point(x=750, y=225), room_id=room.id),
        ],
    )
    results = validate_design(building, design, "india_nbc_2016")
    rule_ids = {result.rule_id for result in results if result.severity.value == "ERROR"}
    assert "ROOM_MIN_AREA" in rule_ids or "ROOM_MIN_WIDTH" in rule_ids


def test_wrong_pipe_size_and_slope_are_errors(tmp_path):
    building, design = sample_design(tmp_path)
    design.pipes[0].diameter_mm = 999
    design.pipes[0].slope = 0.5
    results = validate_design(building, design, "india_nbc_2016")
    errors = {result.rule_id for result in results if result.severity.value == "ERROR"}
    assert "PIPE_DIAMETER" in errors
    assert "PIPE_SLOPE" in errors


def test_missing_pipes_are_errors(tmp_path):
    building, design = sample_design(tmp_path)
    design.pipes = []
    results = validate_design(building, design, "india_nbc_2016")
    assert any(result.rule_id == "PIPE_ROUTING" for result in results)


def test_fixture_side_clearance_is_checked():
    room = Room(
        id="R1",
        name="Bathroom",
        boundary=[
            Point(x=0, y=0),
            Point(x=3000, y=0),
            Point(x=3000, y=2400),
            Point(x=0, y=2400),
        ],
    )
    building = Building(id="B1", rooms=[room])
    fixture = make_fixture("WC-01", FixtureType.WC, Point(x=200, y=350), room_id="R1")
    design = Design(
        room_id="R1",
        profile_id="india_nbc_2016",
        stack=Stack(id="S1", position=Point(x=2600, y=300)),
        fixtures=[fixture],
    )
    results = validate_design(building, design, "india_nbc_2016")
    side = next(result for result in results if result.rule_id == "FIXTURE_SIDE_CLEARANCE")
    assert side.severity.value in ("ERROR", "WARNING")
