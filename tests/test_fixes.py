from core.dxf_import import import_dxf
from core.fixes import apply_fix, recommend_fixes
from core.layout import generate_layouts
from core.models import Design, FixtureType, Stack
from core.router import route_design
from core.rules.engine import load_profile, summarize, validate_design
from core.sample_plan import build_apartment


def sample(tmp_path):
    path = tmp_path / "apartment.dxf"
    build_apartment(path)
    building = import_dxf(path)
    room = next(room for room in building.rooms if "bath" in (room.name or "").lower())
    stack = Stack(id="S1", position=building.shafts[0].position)
    candidates = generate_layouts(
        building,
        room.id,
        [FixtureType.WC, FixtureType.BASIN, FixtureType.SHOWER],
        stack.position,
    )
    profile = load_profile("india_nbc_2016")
    design = Design(
        room_id=room.id,
        profile_id=profile.id,
        stack=stack,
        fixtures=candidates[0].fixtures,
        layout_id=candidates[0].id,
    )
    route_design(building, design, profile)
    return building, design, candidates, profile


def test_recommend_and_apply_candidate_switch(tmp_path):
    building, design, candidates, profile = sample(tmp_path)
    before = validate_design(building, design, profile)
    fixes = recommend_fixes(building, design, before, profile, candidates)

    switch = next(fix for fix in fixes if fix.kind == "SELECT_CANDIDATE")
    updated = apply_fix(building, design, switch, profile, candidates)
    after = validate_design(building, updated, profile)

    assert summarize(after)["ERROR"] <= summarize(before)["ERROR"]
    assert summarize(after)["WARNING"] <= summarize(before)["WARNING"]
    assert updated.layout_id == switch.params["candidate_id"]


def test_slope_and_size_fixes(tmp_path):
    building, design, candidates, profile = sample(tmp_path)
    design.pipes[0].slope = 0.5
    design.pipes[0].diameter_mm = 999
    results = validate_design(building, design, profile)
    fixes = recommend_fixes(building, design, results, profile, candidates)
    kinds = {fix.kind for fix in fixes}
    assert "ADJUST_SLOPE" in kinds
    assert "CHANGE_PIPE_SIZE" in kinds

    updated = design
    for fix in fixes:
        if fix.kind in ("ADJUST_SLOPE", "CHANGE_PIPE_SIZE"):
            updated = apply_fix(building, updated, fix, profile, candidates)
    after = validate_design(building, updated, profile)
    assert summarize(after)["ERROR"] == 0


def test_route_fix_when_pipes_missing(tmp_path):
    building, design, candidates, profile = sample(tmp_path)
    design.pipes = []
    results = validate_design(building, design, profile)
    fixes = recommend_fixes(building, design, results, profile, candidates)
    route = next(fix for fix in fixes if fix.kind == "ROUTE_DRAINAGE")
    updated = apply_fix(building, design, route, profile, candidates)
    assert len(updated.pipes) == 3
