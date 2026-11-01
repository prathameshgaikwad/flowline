import ezdxf

from core.dxf_import import import_dxf
from core.geometry import Point
from core.layout import generate_layouts
from core.models import Design, FixtureType, RoomPlan, Stack
from core.plumbing import build_plumbing
from core.router import route_design
from core.rules.engine import load_profile
from core.sample_plan import build_apartment
from core.sheet import _design_bbox, prepare_sheet
from core.svg import render_svg
from tests.test_consolidated_plumbing import _two_room_design


def test_svg_renders_every_stack_and_room():
    building, design = _two_room_design()
    profile = load_profile("india_nbc_2016")
    route_design(building, design, profile)
    build_plumbing(building, design, profile)

    svg = render_svg(building, design)

    assert "Stack S1" in svg
    assert "Stack S2" in svg
    assert "Vent stack VS1" in svg
    assert "Vent stack VS2" in svg
    assert "WC-01" in svg
    assert "SINK-01" in svg


def test_design_bbox_covers_all_selected_rooms():
    building, design = _two_room_design()

    box = _design_bbox(building, design)

    assert box.minx <= 0
    assert box.maxx >= 8000
    assert box.maxy >= 2400


def test_consolidated_sheet_includes_two_rooms_and_stacks(tmp_path):
    source = tmp_path / "apartment.dxf"
    build_apartment(source)
    building = import_dxf(source)
    bathroom = next(room for room in building.rooms if room.name == "BATHROOM")
    kitchen = next(room for room in building.rooms if room.name == "KITCHEN")
    stacks = [
        Stack(id="S1", position=building.shafts[0].position),
        Stack(id="S2", position=building.shafts[0].position),
    ]
    bathroom_candidate = generate_layouts(
        building,
        bathroom.id,
        [item for item in bathroom.default_fixtures],
        stacks[0].position,
    )[0]
    kitchen_candidate = generate_layouts(
        building,
        kitchen.id,
        [item for item in kitchen.default_fixtures],
        stacks[1].position,
    )[0]
    design = Design(
        id="DESIGN-SHEET",
        room_id=bathroom.id,
        profile_id="india_nbc_2016",
        room_plans=[
            RoomPlan(
                room_id=bathroom.id,
                fixture_types=bathroom.default_fixtures,
                layout_id=bathroom_candidate.id,
                stack_id="S1",
            ),
            RoomPlan(
                room_id=kitchen.id,
                fixture_types=kitchen.default_fixtures,
                layout_id=kitchen_candidate.id,
                stack_id="S2",
            ),
        ],
        stacks=stacks,
        stack=stacks[0],
        fixtures=[
            fixture.model_copy(update={"room_id": bathroom.id}, deep=True)
            for fixture in bathroom_candidate.fixtures
        ]
        + [
            fixture.model_copy(update={"room_id": kitchen.id}, deep=True)
            for fixture in kitchen_candidate.fixtures
        ],
    )
    design.sheet.title = "Floor Plumbing Plan"
    profile = load_profile("india_nbc_2016")
    route_design(building, design, profile)
    build_plumbing(building, design, profile)

    result = prepare_sheet(
        building,
        design,
        profile,
        source,
        tmp_path / "sheet",
    )

    assert result.pages >= 1
    doc = ezdxf.readfile(result.dxf_path)
    inserts = [
        entity.dxf.name
        for entity in doc.modelspace()
        if entity.dxftype() == "INSERT"
    ]
    assert inserts.count("FL-STACK") == 2
    assert inserts.count("FL-VENT-STACK") == 2
    assert "FL-WC" in inserts
    assert "FL-KITCHEN-SINK" in inserts
    paper_text = " ".join(
        entity.dxf.text
        for layout in doc.layouts
        for entity in layout.query("TEXT")
    )
    assert "Floor Plumbing Plan" in paper_text
    assert "ROOM" in paper_text


def test_riser_lists_every_stack(tmp_path):
    source = tmp_path / "apartment.dxf"
    build_apartment(source)
    building = import_dxf(source)
    bathroom = next(room for room in building.rooms if room.name == "BATHROOM")
    stack_positions = [
        building.shafts[0].position,
        Point(x=5000, y=1000),
        Point(x=5000, y=2500),
        Point(x=1000, y=2500),
    ]
    stacks = [
        Stack(id=f"S{index}", position=position)
        for index, position in enumerate(stack_positions, start=1)
    ]
    candidate = generate_layouts(
        building,
        bathroom.id,
        [item for item in bathroom.default_fixtures],
        stacks[0].position,
    )[0]
    design = Design(
        room_id=bathroom.id,
        profile_id="india_nbc_2016",
        room_plans=[
            RoomPlan(
                room_id=bathroom.id,
                fixture_types=bathroom.default_fixtures,
                layout_id=candidate.id,
                stack_id="S1",
            )
        ],
        stacks=stacks,
        stack=stacks[0],
        fixtures=[
            fixture.model_copy(update={"room_id": bathroom.id}, deep=True)
            for fixture in candidate.fixtures
        ],
    )
    profile = load_profile("india_nbc_2016")
    route_design(building, design, profile)
    build_plumbing(building, design, profile)

    result = prepare_sheet(building, design, profile, source, tmp_path / "sheet")
    doc = ezdxf.readfile(result.dxf_path)
    paper_text = " ".join(
        entity.dxf.text
        for layout in doc.layouts
        for entity in layout.query("TEXT")
    )

    assert all(f"S{index}" in paper_text for index in range(1, 5))


def test_floor_drain_only_sheet_does_not_require_water_or_vent(tmp_path):
    from core.fixtures import make_fixture

    source = tmp_path / "apartment.dxf"
    build_apartment(source)
    building = import_dxf(source)
    bathroom = next(room for room in building.rooms if room.name == "BATHROOM")
    stack = Stack(id="S1", position=building.shafts[0].position)
    design = Design(
        room_id=bathroom.id,
        profile_id="india_nbc_2016",
        room_plans=[
            RoomPlan(
                room_id=bathroom.id,
                fixture_types=[FixtureType.FLOOR_DRAIN],
                layout_id="C-01",
                stack_id="S1",
            )
        ],
        stacks=[stack],
        stack=stack,
        fixtures=[
            make_fixture(
                "FD-01",
                FixtureType.FLOOR_DRAIN,
                building.shafts[0].position,
                room_id=bathroom.id,
            )
        ],
    )
    profile = load_profile("india_nbc_2016")
    route_design(building, design, profile)
    build_plumbing(building, design, profile)

    result = prepare_sheet(building, design, profile, source, tmp_path / "sheet")
    service_checks = [
        check
        for check in result.review
        if check.rule_id in {"SHEET_SERVICES", "SHEET_WATER"}
    ]

    assert service_checks
    assert all(check.severity == "PASS" for check in service_checks)
