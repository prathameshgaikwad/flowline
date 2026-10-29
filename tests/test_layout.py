from core.dxf_import import import_dxf
from core.geometry import Point, inflate_bbox, rects_overlap
from core.layout import generate_layouts
from core.models import FixtureType
from core.sample_plan import build_apartment, build_tight_bathroom


def bathroom_and_stack(tmp_path):
    path = tmp_path / "apartment.dxf"
    build_apartment(path)
    building = import_dxf(path)
    room = next(room for room in building.rooms if "bath" in (room.name or "").lower())
    stack = building.shafts[0].position
    return building, room, stack


def test_generates_at_least_three_ranked_candidates(tmp_path):
    building, room, stack = bathroom_and_stack(tmp_path)
    candidates = generate_layouts(
        building, room.id, [FixtureType.WC, FixtureType.BASIN, FixtureType.SHOWER], stack
    )

    assert len(candidates) >= 3
    assert candidates[0].score >= candidates[-1].score
    assert all(len(candidate.fixtures) == 3 for candidate in candidates)
    assert {fixture.type for fixture in candidates[0].fixtures} == {
        FixtureType.WC,
        FixtureType.BASIN,
        FixtureType.SHOWER,
    }


def test_valid_candidates_do_not_overlap_or_leave_the_room(tmp_path):
    building, room, stack = bathroom_and_stack(tmp_path)
    candidates = generate_layouts(
        building, room.id, [FixtureType.WC, FixtureType.BASIN, FixtureType.SHOWER], stack
    )
    valid = [candidate for candidate in candidates if not candidate.violations]
    assert valid

    for candidate in valid:
        for fixture in candidate.fixtures:
            box = fixture.bbox
            assert room.bbox.contains(Point(x=box.minx, y=box.miny), tolerance=1)
            assert room.bbox.contains(Point(x=box.maxx, y=box.maxy), tolerance=1)
        for index, fixture in enumerate(candidate.fixtures):
            for other in candidate.fixtures[index + 1 :]:
                assert not rects_overlap(
                    inflate_bbox(fixture.bbox, 10), inflate_bbox(other.bbox, 10)
                )


def test_layouts_are_deterministic(tmp_path):
    building, room, stack = bathroom_and_stack(tmp_path)
    first = generate_layouts(
        building, room.id, [FixtureType.WC, FixtureType.BASIN, FixtureType.SHOWER], stack
    )
    second = generate_layouts(
        building, room.id, [FixtureType.WC, FixtureType.BASIN, FixtureType.SHOWER], stack
    )
    assert [c.model_dump() for c in first] == [c.model_dump() for c in second]


def test_tight_room_reports_infeasible_or_violations(tmp_path):
    path = tmp_path / "tight.dxf"
    build_tight_bathroom(path)
    building = import_dxf(path)
    room = building.rooms[0]
    stack = building.shafts[0].position
    candidates = generate_layouts(
        building, room.id, [FixtureType.WC, FixtureType.BASIN, FixtureType.SHOWER], stack
    )
    assert candidates == [] or all(candidate.violations for candidate in candidates)
