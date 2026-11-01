import xml.etree.ElementTree as ET

from core.dxf_import import import_dxf
from core.fixtures import make_fixture
from core.geometry import Point
from core.models import (
    Building,
    Design,
    DetectedFixture,
    FixtureType,
    Pipe,
    Room,
    Shaft,
    ShaftService,
    Stack,
    System,
)
from core.sample_plan import build_apartment
from core.svg import render_svg


def test_renders_plan_with_rooms_doors_and_shaft(tmp_path):
    path = tmp_path / "apartment.dxf"
    build_apartment(path)
    building = import_dxf(path)

    svg = render_svg(building)

    ET.fromstring(svg)
    assert svg.startswith("<svg")
    assert svg.count('class="room"') >= 3
    assert "BATHROOM" in svg
    assert 'class="bg door-line"' in svg
    assert 'class="shaft"' in svg


def test_renders_detected_fixtures_and_shaft_service_ports():
    room = Room(
        id="R-01",
        name="BATHROOM",
        boundary=[
            Point(x=0, y=0),
            Point(x=2400, y=0),
            Point(x=2400, y=1800),
            Point(x=0, y=1800),
        ],
    )
    shaft = Shaft(
        id="S1",
        position=Point(x=2700, y=300),
        width_mm=600,
        depth_mm=600,
        services=[
            ShaftService.DRAIN,
            ShaftService.WATER,
            ShaftService.VENT,
        ],
        source="inferred_hatch",
    )
    building = Building(
        rooms=[room],
        shafts=[shaft],
        detected_fixtures=[
            DetectedFixture(
                id="F-01-WC",
                type=FixtureType.WC,
                room_id="R-01",
                position=Point(x=700, y=900),
                width_mm=650,
                depth_mm=550,
                source="geometry",
            ),
            DetectedFixture(
                id="F-02-BASIN",
                type=FixtureType.BASIN,
                room_id="R-01",
                position=Point(x=1700, y=900),
                width_mm=340,
                depth_mm=528,
                source="geometry",
            ),
        ],
    )

    svg = render_svg(building)

    ET.fromstring(svg)
    assert 'class="detected-fixture detected-fixture-WC"' in svg
    assert 'class="detected-fixture detected-fixture-BASIN"' in svg
    assert ">WC<" in svg
    assert ">BASIN<" in svg
    assert 'class="shaft-service shaft-service-drain"' in svg
    assert 'class="shaft-service shaft-service-water"' in svg
    assert 'class="shaft-service shaft-service-vent"' in svg


def test_renders_design_overlay(tmp_path):
    path = tmp_path / "apartment.dxf"
    build_apartment(path)
    building = import_dxf(path)
    stack = Stack(id="S1", position=Point(x=2200, y=150))
    wc = make_fixture("WC-01", FixtureType.WC, Point(x=500, y=350), room_id="R-01")
    basin = make_fixture("BASIN-01", FixtureType.BASIN, Point(x=1500, y=225), room_id="R-01")
    design = Design(
        room_id="R-01",
        profile_id="india_nbc_2016",
        stack=stack,
        fixtures=[wc, basin],
        pipes=[
            Pipe(
                id="P-01",
                system=System.SOIL,
                diameter_mm=100,
                points=[Point(x=690, y=350), Point(x=2200, y=350), Point(x=2200, y=150)],
                slope=0.02,
                from_node="WC-01",
                to_node="S1",
            )
        ],
    )

    svg = render_svg(building, design)

    ET.fromstring(svg)
    assert 'class="fixture fixture-WC"' in svg
    assert 'class="fixture fixture-BASIN"' in svg
    assert 'class="pipe pipe-SOIL"' in svg
    assert 'class="stack"' in svg
    assert "100mm" in svg
