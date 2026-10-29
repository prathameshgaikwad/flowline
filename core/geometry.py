from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from pydantic import BaseModel, ConfigDict


class Point(BaseModel):
    model_config = ConfigDict(frozen=True)
    x: float
    y: float


@dataclass(frozen=True)
class BBox:
    minx: float
    miny: float
    maxx: float
    maxy: float

    @property
    def width(self) -> float:
        return self.maxx - self.minx

    @property
    def height(self) -> float:
        return self.maxy - self.miny

    @property
    def center(self) -> Point:
        return Point(x=(self.minx + self.maxx) / 2.0, y=(self.miny + self.maxy) / 2.0)

    def contains(self, point: Point, tolerance: float = 0.0) -> bool:
        return (
            self.minx - tolerance <= point.x <= self.maxx + tolerance
            and self.miny - tolerance <= point.y <= self.maxy + tolerance
        )


def polygon_area(points: Sequence[Point]) -> float:
    if len(points) < 3:
        return 0.0
    total = 0.0
    for index, current in enumerate(points):
        nxt = points[(index + 1) % len(points)]
        total += current.x * nxt.y - nxt.x * current.y
    return abs(total) / 2.0


def bbox(points: Sequence[Point]) -> BBox:
    if not points:
        return BBox(0.0, 0.0, 0.0, 0.0)
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    return BBox(min(xs), min(ys), max(xs), max(ys))


def rect_corners(x: float, y: float, width: float, height: float) -> list[Point]:
    return [
        Point(x=x, y=y),
        Point(x=x + width, y=y),
        Point(x=x + width, y=y + height),
        Point(x=x, y=y + height),
    ]


def rects_overlap(a: BBox, b: BBox, tolerance: float = 0.0) -> bool:
    return not (
        a.maxx <= b.minx + tolerance
        or b.maxx <= a.minx + tolerance
        or a.maxy <= b.miny + tolerance
        or b.maxy <= a.miny + tolerance
    )


def inflate_bbox(box: BBox, amount: float) -> BBox:
    return BBox(box.minx - amount, box.miny - amount, box.maxx + amount, box.maxy + amount)


def point_on_segment(point: Point, start: Point, end: Point, tolerance: float = 1e-6) -> bool:
    cross = (point.y - start.y) * (end.x - start.x) - (point.x - start.x) * (end.y - start.y)
    if abs(cross) > tolerance:
        return False
    dot = (point.x - start.x) * (end.x - start.x) + (point.y - start.y) * (end.y - start.y)
    if dot < -tolerance:
        return False
    length_sq = (end.x - start.x) ** 2 + (end.y - start.y) ** 2
    return dot <= length_sq + tolerance


def point_in_polygon(point: Point, polygon: Sequence[Point], tolerance: float = 1e-6) -> bool:
    if len(polygon) < 3:
        return False
    vertices = list(polygon)
    if len(vertices) >= 2 and distance(vertices[0], vertices[-1]) <= tolerance:
        vertices = vertices[:-1]
    if len(vertices) < 3:
        return False
    for index, current in enumerate(vertices):
        nxt = vertices[(index + 1) % len(vertices)]
        if point_on_segment(point, current, nxt, tolerance):
            return True
    inside = False
    j = len(vertices) - 1
    for i, current in enumerate(vertices):
        previous = vertices[j]
        if (current.y > point.y) != (previous.y > point.y):
            intersection_x = (
                (previous.x - current.x)
                * (point.y - current.y)
                / (previous.y - current.y)
                + current.x
            )
            if point.x < intersection_x:
                inside = not inside
        j = i
    return inside


def segment_intersects_bbox(start: Point, end: Point, box: BBox) -> bool:
    if box.contains(start) or box.contains(end):
        return True
    dx = end.x - start.x
    dy = end.y - start.y
    t0, t1 = 0.0, 1.0
    for p, q in (
        (-dx, start.x - box.minx),
        (dx, box.maxx - start.x),
        (-dy, start.y - box.miny),
        (dy, box.maxy - start.y),
    ):
        if abs(p) < 1e-12:
            if q < 0:
                return False
            continue
        ratio = q / p
        if p < 0:
            t0 = max(t0, ratio)
        else:
            t1 = min(t1, ratio)
        if t0 > t1:
            return False
    return True


def distance(a: Point, b: Point) -> float:
    return math.hypot(b.x - a.x, b.y - a.y)


def manhattan(a: Point, b: Point) -> float:
    return abs(b.x - a.x) + abs(b.y - a.y)


def polyline_length(points: Sequence[Point]) -> float:
    return sum(distance(points[index], points[index + 1]) for index in range(len(points) - 1))


def dedupe_collinear(points: Sequence[Point], tolerance: float = 1e-6) -> list[Point]:
    if len(points) < 3:
        return list(points)
    result = [points[0]]
    for index in range(1, len(points) - 1):
        previous = result[-1]
        current = points[index]
        nxt = points[index + 1]
        cross = (current.x - previous.x) * (nxt.y - current.y) - (
            current.y - previous.y
        ) * (nxt.x - current.x)
        same_direction = (current.x - previous.x) * (nxt.x - current.x) + (
            current.y - previous.y
        ) * (nxt.y - current.y) >= 0
        if abs(cross) > tolerance or not same_direction:
            result.append(current)
    result.append(points[-1])
    return result
