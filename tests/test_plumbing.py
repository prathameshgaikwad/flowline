from core.dxf_import import import_dxf
from core.layout import generate_layouts
from core.models import Design, FixtureType, PlumbingItemType, Stack, SupplySystem
from core.plumbing import build_plumbing
from core.router import route_design
from core.rules.engine import load_profile, summarize, validate_design
from core.sample_plan import build_apartment


def _sample(tmp_path):
    source = tmp_path / "apartment.dxf"
    build_apartment(source)
    building = import_dxf(source)
    profile = load_profile("india_nbc_2016")
    room = next(room for room in building.rooms if room.is_wet_area)
    stack = Stack(id="S1", position=building.shafts[0].position)
    candidates = generate_layouts(
        building,
        room.id,
        [FixtureType.WC, FixtureType.BASIN, FixtureType.SHOWER],
        stack.position,
    )
    candidate = candidates[0]
    design = Design(
        id="DESIGN-TEST",
        room_id=room.id,
        profile_id=profile.id,
        stack=stack,
        fixtures=[fixture.model_copy(deep=True) for fixture in candidate.fixtures],
        layout_id=candidate.id,
        rationale="Test.",
    )
    route_design(building, design, profile)
    return building, design, profile


def test_build_plumbing_routes_vent_and_hot_cold_water(tmp_path):
    building, design, profile = _sample(tmp_path)
    build_plumbing(building, design, profile)

    assert design.vent_stack is not None
    assert design.water_source is not None
    assert len(design.vent_pipes) == 3
    assert {pipe.system for pipe in design.supply_pipes} == {
        SupplySystem.COLD,
        SupplySystem.HOT,
    }
    assert any(
        pipe.system == SupplySystem.COLD and pipe.to_node == "WC-B1"
        for pipe in design.supply_pipes
    )
    assert any(
        pipe.system == SupplySystem.HOT and pipe.to_node == "BASIN-R1"
        for pipe in design.supply_pipes
    )
    types = {item.type for item in design.plumbing_items}
    assert PlumbingItemType.MAIN_SHUTOFF in types
    assert PlumbingItemType.CLEANOUT in types
    assert PlumbingItemType.WATER_HEATER in types


def test_full_services_have_no_validation_errors(tmp_path):
    building, design, profile = _sample(tmp_path)
    build_plumbing(building, design, profile)
    counts = summarize(validate_design(building, design, profile))
    assert counts["ERROR"] == 0


def test_missing_services_are_warnings_not_errors(tmp_path):
    building, design, profile = _sample(tmp_path)
    counts = summarize(validate_design(building, design, profile))
    assert counts["ERROR"] == 0
    assert counts["WARNING"] >= 1
