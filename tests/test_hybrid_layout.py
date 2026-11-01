import ezdxf

from core.dxf_import import import_dxf
from core.geometry import Point
from core.layout import generate_layouts
from core.models import FixtureType


def _build_detected_bathroom(path, wc_position=(900, 275), basin_position=(1700, 264)):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (3000, 0), (3000, 2400), (0, 2400)],
        close=True,
        dxfattribs={"layer": "A-ROOM"},
    )
    msp.add_text(
        "BATHROOM", dxfattribs={"layer": "A-TEXT", "height": 150}
    ).set_placement((1500, 1200))

    wc = doc.blocks.new("A$C_WC")
    wc.add_lwpolyline(
        [(-325, -275), (325, -275), (325, 275), (-325, 275)],
        close=True,
    )
    msp.add_blockref(
        "A$C_WC",
        wc_position,
        dxfattribs={"layer": "M03 Sanitaryware"},
    )

    basin = doc.blocks.new("Cubica")
    basin.add_lwpolyline(
        [(-170, -264), (170, -264), (170, 264), (-170, 264)],
        close=True,
    )
    msp.add_blockref(
        "Cubica",
        basin_position,
        dxfattribs={"layer": "M03 Sanitaryware"},
    )
    doc.saveas(path)
    return import_dxf(path)


def test_valid_source_fixtures_become_the_preferred_layout(tmp_path):
    path = tmp_path / "source_layout.dxf"
    building = _build_detected_bathroom(path)
    room = building.rooms[0]

    candidates = generate_layouts(
        building,
        room.id,
        [FixtureType.WC, FixtureType.BASIN],
        Point(x=2800, y=200),
    )

    assert candidates
    assert candidates[0].pattern == "existing"
    selected = {fixture.type: fixture for fixture in candidates[0].fixtures}
    assert selected[FixtureType.WC].position.x == 900
    assert selected[FixtureType.WC].position.y == 275
    assert selected[FixtureType.BASIN].position.x == 1700
    assert all(fixture.source == "existing" for fixture in candidates[0].fixtures)


def test_invalid_source_arrangement_is_kept_but_not_preferred(tmp_path):
    path = tmp_path / "invalid_source_layout.dxf"
    building = _build_detected_bathroom(path, wc_position=(200, 275))
    room = building.rooms[0]

    candidates = generate_layouts(
        building,
        room.id,
        [FixtureType.WC, FixtureType.BASIN],
        Point(x=2800, y=200),
    )

    assert candidates
    assert candidates[0].pattern != "existing"
    existing = next(candidate for candidate in candidates if candidate.pattern == "existing")
    assert existing.violations
