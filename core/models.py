from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from core.geometry import BBox, Point, bbox, point_in_polygon, polygon_area
from core.plumbing_zones import PlumbingRole, classify_room, default_fixtures


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


class SupplySystem(StrEnum):
    COLD = "COLD_WATER"
    HOT = "HOT_WATER"


class PlumbingItemType(StrEnum):
    WATER_HEATER = "WATER_HEATER"
    EXPANSION_TANK = "EXPANSION_TANK"
    MAIN_SHUTOFF = "MAIN_SHUTOFF"
    FIXTURE_STOP = "FIXTURE_STOP"
    CHECK_VALVE = "CHECK_VALVE"
    BACKFLOW_PREVENTER = "BACKFLOW_PREVENTER"
    PRESSURE_REDUCING_VALVE = "PRESSURE_REDUCING_VALVE"
    CLEANOUT = "CLEANOUT"
    TRAP_PRIMER = "TRAP_PRIMER"
    VENT_TERMINATION = "VENT_TERMINATION"
    AIR_ADMITTANCE_VALVE = "AIR_ADMITTANCE_VALVE"


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
    fixture_hints: list[FixtureType] = Field(default_factory=list)
    has_sanitaryware: bool = False

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
    def plumbing_role(self) -> PlumbingRole:
        role = classify_room(self.name, self.fixture_hints)
        if role == PlumbingRole.NONE and self.has_sanitaryware:
            return PlumbingRole.POWDER
        return role

    @property
    def default_fixtures(self) -> list[FixtureType]:
        if self.fixture_hints:
            return list(dict.fromkeys(self.fixture_hints))
        return default_fixtures(self.plumbing_role)

    @property
    def is_wet_area(self) -> bool:
        return self.plumbing_role != PlumbingRole.NONE


class Door(BaseModel):
    id: str
    position: Point
    width_mm: float = 900.0
    wall_id: str | None = None


class ShaftService(StrEnum):
    DRAIN = "DRAIN"
    WATER = "WATER"
    VENT = "VENT"


class Shaft(BaseModel):
    id: str
    position: Point
    width_mm: float = 600.0
    depth_mm: float = 600.0
    name: str | None = None
    services: list[ShaftService] = Field(
        default_factory=lambda: [
            ShaftService.DRAIN,
            ShaftService.WATER,
            ShaftService.VENT,
        ]
    )
    source: str = "explicit"
    confidence: float = 1.0

    @property
    def bbox(self) -> BBox:
        return BBox(
            self.position.x - self.width_mm / 2,
            self.position.y - self.depth_mm / 2,
            self.position.x + self.width_mm / 2,
            self.position.y + self.depth_mm / 2,
        )


class DetectedFixture(BaseModel):
    id: str
    type: FixtureType
    room_id: str | None = None
    position: Point
    width_mm: float
    depth_mm: float
    rotation_deg: float = 0.0
    block_name: str | None = None
    layer: str = "0"
    source: str = "geometry"
    confidence: float = 0.6


class DrawingEntity(BaseModel):
    kind: str
    layer: str = "0"
    role: str = "other"
    points: list[Point] = Field(default_factory=list)
    closed: bool = False
    center: Point | None = None
    radius: float | None = None
    start_angle: float | None = None
    end_angle: float | None = None
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
    detected_fixtures: list[DetectedFixture] = Field(default_factory=list)
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
    source: str = "generated"
    source_fixture_id: str | None = None

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
    room_id: str | None = None


class Stack(BaseModel):
    id: str
    position: Point
    diameter_mm: float = 100.0
    shaft_id: str | None = None


class VentStack(BaseModel):
    id: str = "VS1"
    stack_id: str | None = None
    position: Point
    diameter_mm: float = 50.0
    height_mm: float = 3000.0
    terminates_above_roof: bool = True
    shaft_id: str | None = None


class WaterSource(BaseModel):
    id: str = "WS1"
    position: Point
    pressure_kpa: float = 300.0
    cold_diameter_mm: float = 25.0
    hot_diameter_mm: float = 20.0
    heater: bool = True
    heater_capacity_l: float = 50.0
    heater_fuel: str = "electric"
    material: str = "CPVC"
    shaft_id: str | None = None


class SupplyPipe(BaseModel):
    id: str
    system: SupplySystem
    diameter_mm: float
    points: list[Point] = Field(min_length=2)
    from_node: str
    to_node: str
    material: str = "CPVC"
    insulated: bool = True
    room_id: str | None = None


class PlumbingItem(BaseModel):
    id: str
    type: PlumbingItemType
    position: Point
    tag: str | None = None
    system: str | None = None
    size: str | None = None
    notes: str | None = None
    room_id: str | None = None


class SheetSpec(BaseModel):
    preset: str = "A3"
    width_mm: float = 420.0
    height_mm: float = 297.0
    orientation: str = "landscape"
    scale: float = 50.0
    title: str = "Bathroom Plumbing Plan"
    sheet_number: str = "P-101"
    revision: str = "A"
    drawn_by: str = "Flowline"
    checked_by: str = ""
    include_riser: bool = True
    include_schedules: bool = True
    notes: list[str] = Field(
        default_factory=lambda: [
            "Verify all dimensions and clearances on site.",
            "Provide access to valves, cleanouts, and the vent termination.",
        ]
    )


SHEET_PRESETS_MM: dict[str, tuple[float, float]] = {
    "A4": (210.0, 297.0),
    "A3": (297.0, 420.0),
    "A2": (420.0, 594.0),
    "A1": (594.0, 841.0),
    "A0": (841.0, 1189.0),
    "ANSI_A": (215.9, 279.4),
    "ANSI_B": (279.4, 431.8),
    "ANSI_C": (431.8, 558.8),
    "ANSI_D": (558.8, 863.6),
    "ANSI_E": (863.6, 1117.6),
}


class DrawingCheck(BaseModel):
    rule_id: str
    severity: Severity
    message: str
    affected: dict[str, Any] = Field(default_factory=dict)


class RoomPlan(BaseModel):
    room_id: str
    fixture_types: list[FixtureType] = Field(
        default_factory=lambda: [FixtureType.WC, FixtureType.BASIN, FixtureType.SHOWER]
    )
    layout_id: str | None = None
    stack_id: str = "S1"
    water_source_id: str | None = None
    rationale: str | None = None


class Design(BaseModel):
    id: str = "DESIGN-01"
    room_id: str
    profile_id: str
    layout_id: str | None = None
    room_plans: list[RoomPlan] = Field(default_factory=list)
    fixtures: list[Fixture] = Field(default_factory=list)
    pipes: list[Pipe] = Field(default_factory=list)
    vent_pipes: list[Pipe] = Field(default_factory=list)
    supply_pipes: list[SupplyPipe] = Field(default_factory=list)
    plumbing_items: list[PlumbingItem] = Field(default_factory=list)
    stack: Stack
    stacks: list[Stack] = Field(default_factory=list)
    vent_stack: VentStack | None = None
    vent_stacks: list[VentStack] = Field(default_factory=list)
    water_source: WaterSource | None = None
    water_sources: list[WaterSource] = Field(default_factory=list)
    sheet: SheetSpec = Field(default_factory=SheetSpec)
    rationale: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    route_failures: list[str] = Field(default_factory=list)

    @property
    def room_ids(self) -> list[str]:
        if self.room_plans:
            return [plan.room_id for plan in self.room_plans]
        return [self.room_id] if self.room_id else []

    def fixture(self, fixture_id: str) -> Fixture:
        for fixture in self.fixtures:
            if fixture.id == fixture_id:
                return fixture
        raise KeyError(f"Unknown fixture {fixture_id!r}.")

    def room_plan(self, room_id: str) -> RoomPlan:
        for plan in self.room_plans:
            if plan.room_id == room_id:
                return plan
        raise KeyError(f"Unknown room plan {room_id!r}.")

    def fixtures_for_room(self, room_id: str) -> list[Fixture]:
        return [fixture for fixture in self.fixtures if fixture.room_id == room_id]

    def pipes_for_room(self, room_id: str) -> list[Pipe]:
        return [pipe for pipe in self.pipes if pipe.room_id == room_id]

    def stack_for_room(self, room_id: str) -> Stack:
        plan = next(
            (item for item in self.room_plans if item.room_id == room_id),
            None,
        )
        stack_id = plan.stack_id if plan else self.stack.id
        return next(
            (stack for stack in self.stacks if stack.id == stack_id),
            self.stack,
        )

    def vent_stack_for_room(self, room_id: str) -> VentStack | None:
        stack_id = self.stack_for_room(room_id).id
        return next(
            (item for item in self.vent_stacks if item.stack_id == stack_id),
            self.vent_stack,
        )

    def water_source_for_room(self, room_id: str) -> WaterSource | None:
        plan = next(
            (item for item in self.room_plans if item.room_id == room_id),
            None,
        )
        source_id = plan.water_source_id if plan else None
        if source_id:
            source = next(
                (item for item in self.water_sources if item.id == source_id),
                None,
            )
            if source is not None:
                return source
        if self.water_sources:
            return self.water_sources[0]
        return self.water_source

    def successor_pipes(self, node_id: str) -> list[Pipe]:
        return [pipe for pipe in self.pipes if pipe.from_node == node_id]

    def reaches_stack(self, fixture_id: str) -> bool:
        stack_ids = {stack.id for stack in self.stacks} or {self.stack.id}
        seen: set[str] = set()
        pending = [fixture_id]
        while pending:
            node = pending.pop()
            if node in stack_ids:
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
