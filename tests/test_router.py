import pytest

from core.dxf_import import import_dxf
from core.fixtures import make_fixture
from core.geometry import Point, manhattan, polyline_length
from core.layout import generate_layouts
from core.models import Building, Design, FixtureType, Room, Stack
from core.router import route_design
from core.rules.engine import load_profile
from core.sample_plan import build_apartment


def make_sample_design(tmp_path):
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
        profile_id="india_nbc_2016",
        stack=stack,
        fixtures=candidate.fixtures,
        layout_id=candidate.id,
    )
    return building, design


def test_routes_each_fixture_to_the_stack(tmp_path):
    building, design = make_sample_design(tmp_path)
    profile = load_profile("india_nbc_2016")

    pipes = route_design(building, design, profile)

    assert len(pipes) == 3
    assert design.pipes == pipes
    fixture_ids = {fixture.id for fixture in design.fixtures}
    for pipe in pipes:
        assert pipe.from_node in fixture_ids
        assert pipe.to_node == design.stack.id
        assert pipe.points[0].x == pytest.approx(pipe.points[0].x)
        assert pipe.points[-1] == design.stack.position
        assert pipe.slope and pipe.slope > 0
        assert all(
            pipe.points[i].x == pipe.points[i + 1].x
            or pipe.points[i].y == pipe.points[i + 1].y
            for i in range(len(pipe.points) - 1)
        )
        assert pipe.diameter_mm == profile.pipe_for(
            next(f.type for f in design.fixtures if f.id == pipe.from_node)
        ).diameter_mm


def test_uses_the_selected_profile_sizes(tmp_path):
    building, design = make_sample_design(tmp_path)
    design.profile_id = "us_ipc_2021"
    pipes = route_design(building, design, load_profile("us_ipc_2021"))
    wc_pipe = next(pipe for pipe in pipes if pipe.from_node.startswith("WC"))
    basin_pipe = next(pipe for pipe in pipes if pipe.from_node.startswith("BASIN"))
    assert wc_pipe.diameter_mm == 76
    assert basin_pipe.diameter_mm == 32


def test_route_avoids_fixture_obstacles():
    building = Building(
        id="B1",
        rooms=[
            Room(
                id="R1",
                name="Test",
                boundary=[
                    Point(x=0, y=0),
                    Point(x=4000, y=0),
                    Point(x=4000, y=3000),
                    Point(x=0, y=3000),
                ],
            )
        ],
    )
    wc = make_fixture("WC-01", FixtureType.WC, Point(x=500, y=350), room_id="R1")
    blocker = make_fixture(
        "SHOWER-01", FixtureType.SHOWER, Point(x=2000, y=1500), room_id="R1", rotation_deg=0
    )
    stack = Stack(id="S1", position=Point(x=3500, y=2500))
    design = Design(
        room_id="R1",
        profile_id="india_nbc_2016",
        stack=stack,
        fixtures=[wc, blocker],
    )

    pipes = route_design(building, design, load_profile("india_nbc_2016"))
    wc_pipe = next(pipe for pipe in pipes if pipe.from_node == "WC-01")

    assert polyline_length(wc_pipe.points) > manhattan(
        wc.drain_point(stack.position), stack.position
    )


def test_stack_outside_room_uses_a_corridor():
    building = Building(
        id="B1",
        rooms=[
            Room(
                id="R1",
                name="Tiny",
                boundary=[
                    Point(x=0, y=0),
                    Point(x=4000, y=0),
                    Point(x=4000, y=3000),
                    Point(x=0, y=3000),
                ],
            )
        ],
    )
    fixture = make_fixture("WC-01", FixtureType.WC, Point(x=500, y=350), room_id="R1")
    stack = Stack(id="S1", position=Point(x=4800, y=1800))
    design = Design(
        room_id="R1",
        profile_id="india_nbc_2016",
        stack=stack,
        fixtures=[fixture],
    )
    pipes = route_design(building, design, load_profile("india_nbc_2016"))
    assert pipes[0].points[-1] == stack.position
