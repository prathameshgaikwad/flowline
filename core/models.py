from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from core.geometry import BBox, Point, bbox, point_in_polygon, polygon_area


class FixtureType(StrEnum):
    WC = "WC"
    BASIN = "BASIN"
    SHOWER = "SHOWER"
    FLOOR_DRAIN = "FLOOR_DRAIN"
    KITCHEN_SINK = "KITCHEN_SINK"


class System(StrEnum):
    SOIL = "SOIL"
    WASTE = "WASTE"
    VENT = "VENT"


class Severity(StrEnum):
    PASS = "PASS"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Room(BaseModel):
    id: str
    name: str | None = None
    floor_id: str = "F-01"
    boundary: list[Point] = Field(min_length=3)
    closed: bool = True

    @property
    def is_closed(self) -> bool:
        if self.closed:
            return True
        return len(self.boundary) >= 4 and _same_point(self.boundary[0], self.boundary[-1])

    @property
    def area_mm2(self) -> float:
        return polygon_area(self.boundary)

    @property
    def area_m2(self) -> float:
        return self.area_mm2 / 1_000_000.0

    @property
    def bbox(self) -> BBox:
        return bbox(self.boundary)

    def contains(self, point: Point) -> bool:
        return point_in_polygon(point, self.boundary)

    @property
    def is_wet_area(self) -> bool:
        name = (self.name or "").lower()
        return any(token in name for token in ("bath", "toilet", "wc", "shower", "wash"))


class Door(BaseModel):
    id: str
    position: Point
    width_mm: float = 900.0
    wall_id: str | None = None


class Shaft(BaseModel):
    id: str
    position: Point
    width_mm: float = 600.0
    depth_mm: float = 600.0

    @property
    def bbox(self) -> BBox:
        return BBox(
            self.position.x - self.width_mm / 2,
            self.position.y - self.depth_mm / 2,
            self.position.x + self.width_mm / 2,
            self.position.y + self.depth_mm / 2,
        )


class DrawingEntity(BaseModel):
    kind: str
    layer: str = "0"
    points: list[Point] = Field(default_factory=list)
    center: Point | None = None
    radius: float | None = None
    text: str | None = None
    position: Point | None = None
    block_name: str | None = None


class Building(BaseModel):
    id: str = "BLDG-01"
    units: str = "mm"
    source_scale: float = 1.0
    rooms: list[Room] = Field(default_factory=list)
    doors: list[Door] = Field(default_factory=list)
    shafts: list[Shaft] = Field(default_factory=list)
    entities: list[DrawingEntity] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def room(self, room_id: str) -> Room:
        for room in self.rooms:
            if room.id == room_id:
                return room
        raise KeyError(f"Unknown room {room_id!r}.")

    def wet_area_candidates(self) -> list[Room]:
        return [room for room in self.rooms if room.is_wet_area]


class Fixture(BaseModel):
    id: str
    type: FixtureType
    position: Point
    rotation_deg: float = 0.0
    width_mm: float = 380.0
    depth_mm: float = 700.0
    room_id: str | None = None
    wall_id: str | None = None
    has_trap: bool = True

    @property
    def half_extents(self) -> tuple[float, float]:
        if int(round(self.rotation_deg)) % 180 == 90:
            return self.depth_mm / 2, self.width_mm / 2
        return self.width_mm / 2, self.depth_mm / 2

    @property
    def bbox(self) -> BBox:
        half_x, half_y = self.half_extents
        return BBox(
            self.position.x - half_x,
            self.position.y - half_y,
            self.position.x + half_x,
            self.position.y + half_y,
        )

    def drain_point(self, stack: Point) -> Point:
        dx = stack.x - self.position.x
        dy = stack.y - self.position.y
        if abs(dx) < 1e-9 and abs(dy) < 1e-9:
            return self.position
        half_x, half_y = self.half_extents
        t_x = half_x / abs(dx) if abs(dx) > 1e-9 else float("inf")
        t_y = half_y / abs(dy) if abs(dy) > 1e-9 else float("inf")
        t = min(t_x, t_y)
        return Point(x=self.position.x + dx * t, y=self.position.y + dy * t)


class Pipe(BaseModel):
    id: str
    system: System
    diameter_mm: float
    points: list[Point] = Field(min_length=2)
    slope: float | None = None
    from_node: str
    to_node: str


class Stack(BaseModel):
    id: str
    position: Point
    diameter_mm: float = 100.0


class Design(BaseModel):
    id: str = "DESIGN-01"
    room_id: str
    profile_id: str
    layout_id: str | None = None
    fixtures: list[Fixture] = Field(default_factory=list)
    pipes: list[Pipe] = Field(default_factory=list)
    stack: Stack
    rationale: str | None = None
    assumptions: list[str] = Field(default_factory=list)

    def fixture(self, fixture_id: str) -> Fixture:
        for fixture in self.fixtures:
            if fixture.id == fixture_id:
                return fixture
        raise KeyError(f"Unknown fixture {fixture_id!r}.")

    def successor_pipes(self, node_id: str) -> list[Pipe]:
        return [pipe for pipe in self.pipes if pipe.from_node == node_id]

    def reaches_stack(self, fixture_id: str) -> bool:
        seen: set[str] = set()
        pending = [fixture_id]
        while pending:
            node = pending.pop()
            if node == self.stack.id:
                return True
            if node in seen:
                continue
            seen.add(node)
            pending.extend(pipe.to_node for pipe in self.successor_pipes(node))
        return False


class ValidationResult(BaseModel):
    rule_id: str
    severity: Severity
    message: str
    source: str
    measured: float | str | None = None
    required: float | str | None = None
    affected: dict[str, Any] = Field(default_factory=dict)
    fix_ids: list[str] = Field(default_factory=list)


class Fix(BaseModel):
    id: str
    kind: str
    description: str
    affected: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)


class LayoutCandidate(BaseModel):
    id: str
    pattern: str
    fixtures: list[Fixture]
    score: float
    violations: list[str] = Field(default_factory=list)
    rationale_hint: str = ""


def _same_point(a: Point, b: Point, tolerance: float = 1e-6) -> bool:
    return abs(a.x - b.x) <= tolerance and abs(a.y - b.y) <= tolerance
