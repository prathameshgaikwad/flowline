import ezdxf

from core.dxf_import import import_dxf
from core.layout import generate_layouts
from core.models import Design, FixtureType, SheetSpec, Stack
from core.plumbing import build_plumbing
from core.router import route_design
from core.rules.engine import load_profile
from core.sample_plan import build_apartment
from core.sheet import prepare_sheet, sheet_counts


def _design(tmp_path):
    source = tmp_path / "apartment.dxf"
    build_apartment(source)
    building = import_dxf(source)
    profile = load_profile("india_nbc_2016")
    stack = Stack(id="S1", position=building.shafts[0].position)
    room = next(room for room in building.rooms if room.is_wet_area)
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
        rationale="Test layout.",
    )
    route_design(building, design, profile)
    build_plumbing(building, design, profile)
    return building, design, profile, source


def test_sheet_build_contains_construction_elements(tmp_path):
    building, design, profile, source = _design(tmp_path)
    result = prepare_sheet(
        building,
        design,
        profile,
        source,
        tmp_path / "out",
        project_name="Test Apartment",
    )

    assert result.pages >= 1
    assert result.svg_paths and result.svg_paths[0].exists()
    assert result.pdf_path.exists() and result.pdf_path.stat().st_size > 0
    counts = sheet_counts(result.review)
    assert counts["ERROR"] == 0

    doc = ezdxf.readfile(result.dxf_path)
    layers = {layer.dxf.name for layer in doc.layers}
    assert {
        "P-SOIL",
        "P-WASTE",
        "P-VENT",
        "P-COLD",
        "P-HOT",
        "P-FIXTURE",
        "P-DIM",
        "P-TITLE",
        "P-SCHEDULE",
    } <= layers
    assert any(entity.dxftype() == "VIEWPORT" for entity in doc.layouts.get(result.layout_names[0]))
    assert any(entity.dxftype() == "DIMENSION" for entity in doc.modelspace())
    assert any(entity.dxftype() == "INSERT" for entity in doc.modelspace())
    text = " ".join(
        entity.dxf.text
        for entity in doc.layouts.get(result.layout_names[0])
        if entity.dxftype() == "TEXT"
    )
    assert "FIXTURE SCHEDULE" in text
    assert "PIPE SCHEDULE" in text
    assert "SHEET" in text
    assert "SCALE" in text

    svg = result.svg_paths[0].read_text(encoding="utf-8")
    assert "<svg" in svg
    assert "420mm" in svg or "297mm" in svg


def test_sheet_supports_presets_and_custom_sizes(tmp_path):
    building, design, profile, source = _design(tmp_path)
    cases = [
        ("A4", "landscape", None, None),
        ("A1", "portrait", None, None),
        ("CUSTOM", "landscape", 500.0, 350.0),
    ]
    for preset, orientation, width, height in cases:
        design.sheet = SheetSpec(
            preset=preset,
            width_mm=width or design.sheet.width_mm,
            height_mm=height or design.sheet.height_mm,
            orientation=orientation,
        )
        result = prepare_sheet(
            building,
            design,
            profile,
            source,
            tmp_path / f"out-{preset}",
            project_name="Test Apartment",
        )
        svg = result.svg_paths[0].read_text(encoding="utf-8")
        assert "<svg" in svg
        if preset == "A4":
            assert "297mm" in svg and "210mm" in svg
            assert result.pages == 2
        elif preset == "A1":
            assert "594mm" in svg and "841mm" in svg
        else:
            assert "500mm" in svg and "350mm" in svg


def test_sheet_review_flags_missing_services(tmp_path):
    source = tmp_path / "apartment.dxf"
    build_apartment(source)
    building = import_dxf(source)
    profile = load_profile("india_nbc_2016")
    room = next(room for room in building.rooms if room.is_wet_area)
    stack = Stack(id="S1", position=building.shafts[0].position)
    design = Design(
        id="DESIGN-TEST",
        room_id=room.id,
        profile_id=profile.id,
        stack=stack,
        fixtures=[],
        layout_id=None,
    )
    result = prepare_sheet(building, design, profile, source, tmp_path / "out")
    ids = {item.rule_id for item in result.review if item.severity.value == "ERROR"}
    assert "SHEET_SERVICES" in ids
    assert "SHEET_WATER" in ids
