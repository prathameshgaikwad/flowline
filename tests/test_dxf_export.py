import ezdxf
import pytest

from core.dxf_export import export_design
from core.dxf_import import import_dxf
from core.fixtures import make_fixture
from core.geometry import Point
from core.models import Design, FixtureType, Pipe, Stack, System
from core.sample_plan import build_apartment


def test_export_preserves_source_and_adds_design_layers(tmp_path):
    source = tmp_path / "apartment.dxf"
    build_apartment(source)
    building = import_dxf(source)
    stack = Stack(id="S1", position=building.shafts[0].position)
    wc = make_fixture("WC-01", FixtureType.WC, Point(x=1200, y=350), room_id="R-01")
    design = Design(
        room_id="R-01",
        profile_id="india_nbc_2016",
        stack=stack,
        fixtures=[wc],
        pipes=[
            Pipe(
                id="P-01",
                system=System.SOIL,
                diameter_mm=100,
                points=[Point(x=1200, y=700), Point(x=1200, y=300), Point(x=2600, y=300)],
                slope=0.0167,
                from_node="WC-01",
                to_node="S1",
            )
        ],
    )
    original_count = len(list(ezdxf.readfile(source).modelspace()))
    target = tmp_path / "design.dxf"
    result = export_design(building, design, source, target)

    assert result == str(target)
    doc = ezdxf.readfile(target)
    layers = {layer.dxf.name for layer in doc.layers}
    assert {"P-SOIL", "P-WASTE", "P-FIXTURE", "P-STACK", "P-TEXT"} <= layers
    assert len(list(doc.modelspace())) > original_count
    assert any(entity.dxf.layer == "P-SOIL" for entity in doc.modelspace())
    assert doc.header["$INSUNITS"] == 4


def test_export_converts_back_to_source_units(tmp_path):
    source = tmp_path / "metres.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (2.4, 0), (2.4, 1.8), (0, 1.8)], close=True, dxfattribs={"layer": "A-ROOM"}
    )
    msp.add_text("BATHROOM", dxfattribs={"layer": "A-TEXT", "height": 0.15}).set_placement(
        (1.2, 0.9)
    )
    doc.saveas(source)
    building = import_dxf(source)
    stack = Stack(id="S1", position=Point(x=2200, y=300))
    wc = make_fixture("WC-01", FixtureType.WC, Point(x=500, y=350), room_id="R-01")
    design = Design(
        room_id=building.rooms[0].id,
        profile_id="india_nbc_2016",
        stack=stack,
        fixtures=[wc],
        pipes=[
            Pipe(
                id="P-01",
                system=System.SOIL,
                diameter_mm=100,
                points=[Point(x=690, y=350), Point(x=2200, y=350), Point(x=2200, y=300)],
                slope=0.0167,
                from_node="WC-01",
                to_node="S1",
            )
        ],
    )
    target = tmp_path / "metres-design.dxf"
    export_design(building, design, source, target)
    exported = ezdxf.readfile(target)
    pipe = next(e for e in exported.modelspace() if e.dxf.layer == "P-SOIL")
    xs = [point[0] for point in pipe.get_points("xy")]
    assert max(xs) == pytest.approx(2.2, abs=1e-6)
