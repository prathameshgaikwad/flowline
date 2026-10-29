import pytest

from core.geometry import (
    BBox,
    Point,
    bbox,
    dedupe_collinear,
    inflate_bbox,
    manhattan,
    point_in_polygon,
    polygon_area,
    polyline_length,
    rect_corners,
    rects_overlap,
    segment_intersects_bbox,
)


def square(size=1000.0):
    return [
        Point(x=0, y=0),
        Point(x=size, y=0),
        Point(x=size, y=size),
        Point(x=0, y=size),
        Point(x=0, y=0),
    ]


def test_polygon_area():
    assert polygon_area(square(2000)) == pytest.approx(4_000_000)
    assert polygon_area(square(2000)[:-1]) == pytest.approx(4_000_000)


def test_point_in_polygon_and_boundary():
    polygon = square(1000)
    assert point_in_polygon(Point(x=500, y=500), polygon)
    assert point_in_polygon(Point(x=0, y=500), polygon)
    assert not point_in_polygon(Point(x=1500, y=500), polygon)


def test_bbox_and_rect_helpers():
    box = bbox(square(1000))
    assert box == BBox(minx=0, miny=0, maxx=1000, maxy=1000)
    assert box.width == 1000
    assert box.height == 1000
    corners = rect_corners(10, 20, 100, 50)
    assert corners[0] == Point(x=10, y=20)
    assert corners[2] == Point(x=110, y=70)


def test_rects_overlap_and_inflate():
    a = BBox(minx=0, miny=0, maxx=100, maxy=100)
    b = BBox(minx=90, miny=90, maxx=200, maxy=200)
    c = BBox(minx=101, miny=101, maxx=200, maxy=200)
    assert rects_overlap(a, b)
    assert not rects_overlap(a, c)
    assert inflate_bbox(a, 10) == BBox(minx=-10, miny=-10, maxx=110, maxy=110)


def test_segment_intersects_bbox():
    box = BBox(minx=0, miny=0, maxx=100, maxy=100)
    assert segment_intersects_bbox(Point(x=-10, y=50), Point(x=110, y=50), box)
    assert not segment_intersects_bbox(Point(x=-10, y=150), Point(x=110, y=150), box)


def test_polyline_helpers():
    points = [
        Point(x=0, y=0),
        Point(x=100, y=0),
        Point(x=200, y=0),
        Point(x=200, y=100),
    ]
    assert polyline_length(points) == pytest.approx(300)
    assert manhattan(points[0], points[-1]) == 300
    assert dedupe_collinear(points) == [
        Point(x=0, y=0),
        Point(x=200, y=0),
        Point(x=200, y=100),
    ]
