from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from core.geometry import Point, inflate_bbox, polyline_length, rects_overlap, segment_intersects_bbox
from core.layout import _door_zone, _front_distance, _side_distance, _stack_zone
from core.models import Building, Design, FixtureType, Severity, System, ValidationResult

PROFILE_DIR = Path(__file__).resolve().parent / "profiles"


class RoomRules(BaseModel):
    model_config = ConfigDict(extra="forbid")
    combined_min_area_m2: float = 0.0
    combined_min_width_mm: float = 0.0
    wc_min_area_m2: float = 0.0
    wc_min_width_mm: float = 0.0
    bathroom_min_area_m2: float = 0.0
    door_min_width_mm: float = 0.0
    source: str


class ClearanceRules(BaseModel):
    model_config = ConfigDict(extra="forbid")
    wc_side_min_mm: float
    wc_side_target_mm: float
    wc_front_min_mm: float
    wc_front_target_mm: float
    basin_side_min_mm: float
    basin_side_target_mm: float
    basin_front_min_mm: float
    basin_front_target_mm: float
    shower_min_mm: float
    shower_target_mm: float
    center_spacing_mm: float
    shower_access_mm: float
    source: str


class PipeRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    system: System
    diameter_mm: float


class SlopeRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    min: float
    max: float
    default: float


class StackRules(BaseModel):
    model_config = ConfigDict(extra="forbid")
    min_diameter_mm: float
    source: str


class VentRules(BaseModel):
    model_config = ConfigDict(extra="forbid")
    min_diameter_mm: float
    max_branch_mm_warning: float
    source: str


class RuleProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    region: str
    status: str
    disclaimer: str
    room: RoomRules
    clearances: ClearanceRules
    pipes: dict[str, PipeRule]
    slopes: dict[str, SlopeRule]
    stack: StackRules
    vent: VentRules
    fixture_units: dict[str, float] = Field(default_factory=dict)
    sources: list[str] = Field(default_factory=list)

    def pipe_for(self, fixture_type: FixtureType | str) -> PipeRule:
        key = fixture_type.value if isinstance(fixture_type, FixtureType) else str(fixture_type)
        try:
            return self.pipes[key]
        except KeyError as exc:
            raise KeyError(f"Profile {self.id} has no pipe rule for {key!r}.") from exc

    def slope_for(self, system: System | str) -> SlopeRule:
        key = system.value if isinstance(system, System) else str(system)
        try:
            return self.slopes[key]
        except KeyError as exc:
            raise KeyError(f"Profile {self.id} has no slope rule for {key!r}.") from exc

    def clearance_for(self, fixture_type: FixtureType | str) -> tuple[float, float]:
        key = fixture_type.value if isinstance(fixture_type, FixtureType) else str(fixture_type)
        if key == "WC":
            return self.clearances.wc_side_min_mm, self.clearances.wc_front_min_mm
        if key == "BASIN":
            return self.clearances.basin_side_min_mm, self.clearances.basin_front_min_mm
        return self.clearances.shower_min_mm, self.clearances.shower_min_mm

    def fixture_unit(self, fixture_type: FixtureType | str) -> float:
        key = fixture_type.value if isinstance(fixture_type, FixtureType) else str(fixture_type)
        return float(self.fixture_units.get(key, 0.0))


@lru_cache(maxsize=None)
def load_profile(profile_id: str) -> RuleProfile:
    path = PROFILE_DIR / f"{profile_id}.yaml"
    if not path.exists():
        available = ", ".join(available_profiles())
        raise KeyError(f"Unknown rule profile {profile_id!r}. Available: {available}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    profile = RuleProfile.model_validate(data)
    if profile.id != profile_id:
        raise ValueError(f"Profile id {profile.id!r} does not match filename {profile_id!r}.")
    return profile


def available_profiles() -> list[str]:
    return sorted(path.stem for path in PROFILE_DIR.glob("*.yaml"))


def validate_design(
    building: Building, design: Design, profile: RuleProfile | str
) -> list[ValidationResult]:
    if isinstance(profile, str):
        profile = load_profile(profile)
    try:
        room = building.room(design.room_id)
    except KeyError:
        return [
            ValidationResult(
                rule_id="ROOM_EXISTS",
                severity=Severity.ERROR,
                message=f"Room {design.room_id!r} is not in the building.",
                source="Flowline",
                affected={"room_id": design.room_id},
            )
        ]

    results: list[ValidationResult] = []
    results.extend(_room_results(building, room, design, profile))
    results.extend(_fixture_results(building, room, design, profile))
    results.extend(_pipe_results(building, room, design, profile))
    return results


def summarize(results: list[ValidationResult]) -> dict[str, int]:
    counts = {"PASS": 0, "WARNING": 0, "ERROR": 0}
    for result in results:
        counts[result.severity.value] += 1
    return counts


def _room_results(building, room, design, profile: RuleProfile) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    results.append(
        _check(
            "ROOM_CLOSED",
            room.is_closed,
            "Room boundary is closed." if room.is_closed else "Room boundary is open.",
            "Flowline import",
            affected={"room_id": room.id},
        )
    )
    box_area = room.bbox.width * room.bbox.height
    if box_area > 0 and room.area_mm2 < box_area * 0.95:
        results.append(
            _check(
                "ROOM_RECTANGULAR",
                False,
                "Room is not a simple rectangle; v1 layout uses its bounding box.",
                "Flowline scope",
                measured=round(room.area_mm2 / box_area, 3),
                required=0.95,
                fail_severity=Severity.WARNING,
                affected={"room_id": room.id},
            )
        )
    else:
        results.append(
            _check(
                "ROOM_RECTANGULAR",
                True,
                "Room is rectangular enough for the v1 layout generator.",
                "Flowline scope",
                affected={"room_id": room.id},
            )
        )

    types = {fixture.type for fixture in design.fixtures}
    if FixtureType.WC in types and (
        FixtureType.BASIN in types or FixtureType.SHOWER in types
    ):
        min_area = profile.room.combined_min_area_m2
        min_width = profile.room.combined_min_width_mm
        label = "combined bathroom"
    elif FixtureType.WC in types:
        min_area = profile.room.wc_min_area_m2
        min_width = profile.room.wc_min_width_mm
        label = "WC"
    else:
        min_area = profile.room.bathroom_min_area_m2
        min_width = profile.room.bathroom_min_width_mm
        label = "bathroom"

    if min_area > 0:
        results.append(
            _check(
                "ROOM_MIN_AREA",
                room.area_m2 + 0.01 >= min_area,
                f"{label} area {room.area_m2:.2f} m2; minimum {min_area:.2f} m2.",
                profile.room.source,
                measured=round(room.area_m2, 3),
                required=min_area,
                affected={"room_id": room.id},
            )
        )
    else:
        results.append(
            _check(
                "ROOM_MIN_AREA",
                True,
                f"{profile.name} does not set a room-area minimum.",
                profile.room.source,
                affected={"room_id": room.id},
            )
        )

    width = min(room.bbox.width, room.bbox.height)
    if min_width > 0:
        results.append(
            _check(
                "ROOM_MIN_WIDTH",
                width + 1 >= min_width,
                f"Room width {width:.0f} mm; minimum {min_width:.0f} mm.",
                profile.room.source,
                measured=width,
                required=min_width,
                affected={"room_id": room.id},
            )
        )

    if not building.doors:
        results.append(
            _check(
                "DOOR_PRESENT",
                False,
                "No door detected; door clearance was not checked.",
                "Flowline import",
                fail_severity=Severity.WARNING,
                fix_ids=["set_door"],
                affected={"room_id": room.id},
            )
        )
    else:
        for door in building.doors:
            results.append(
                _check(
                    "DOOR_WIDTH",
                    door.width_mm + 1 >= profile.room.door_min_width_mm,
                    f"Door {door.id} width {door.width_mm:.0f} mm; minimum "
                    f"{profile.room.door_min_width_mm:.0f} mm.",
                    "NBC 2016 Part 3 / local access rules",
                    measured=door.width_mm,
                    required=profile.room.door_min_width_mm,
                    affected={"door_id": door.id},
                )
            )

    results.append(
        _check(
            "PROFILE_STATUS",
            profile.status != "POC",
            f"Rule pack {profile.id!r} is {profile.status}; "
            "not a compliance certificate.",
            profile.disclaimer,
            measured=profile.status,
            required="verified",
            fail_severity=Severity.WARNING,
            affected={"profile_id": profile.id},
        )
    )

    if not design.fixtures:
        results.append(
            _check(
                "NO_FIXTURES",
                False,
                "Design has no fixtures.",
                "Flowline",
                fix_ids=["select_layout"],
            )
        )
    return results


def _fixture_results(building, room, design, profile: RuleProfile) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    door_zone = _door_zone(building, room)
    stack_zone = _stack_zone(building, room, design.stack.position)

    for fixture in design.fixtures:
        inside = all(
            room.contains(Point(x=x, y=y))
            for x, y in (
                (fixture.bbox.minx, fixture.bbox.miny),
                (fixture.bbox.maxx, fixture.bbox.miny),
                (fixture.bbox.maxx, fixture.bbox.maxy),
                (fixture.bbox.minx, fixture.bbox.maxy),
            )
        )
        results.append(
            _check(
                "FIXTURE_INSIDE_ROOM",
                inside,
                f"{fixture.id} is {'inside' if inside else 'outside'} the room.",
                "Flowline geometry",
                affected={"fixture_id": fixture.id},
                fix_ids=["switch_layout"],
            )
        )
        results.append(
            _check(
                "FIXTURE_TRAP",
                fixture.has_trap,
                f"{fixture.id} {'has' if fixture.has_trap else 'is missing'} a trap.",
                "IPC 1002 / IS 1742",
                affected={"fixture_id": fixture.id},
            )
        )

        if fixture.type in (FixtureType.WC, FixtureType.BASIN):
            if fixture.type == FixtureType.WC:
                side_min = profile.clearances.wc_side_min_mm
                front_min = profile.clearances.wc_front_min_mm
                side_target = profile.clearances.wc_side_target_mm
                front_target = profile.clearances.wc_front_target_mm
            else:
                side_min = profile.clearances.basin_side_min_mm
                front_min = profile.clearances.basin_front_min_mm
                side_target = profile.clearances.basin_side_target_mm
                front_target = profile.clearances.basin_front_target_mm

            side = _side_distance(fixture, room.bbox)
            front = _front_distance(fixture, room.bbox)
            results.append(
                _clearance_result(
                    "FIXTURE_SIDE_CLEARANCE",
                    fixture,
                    side,
                    side_min,
                    side_target,
                    profile,
                    "side",
                )
            )
            results.append(
                _clearance_result(
                    "FIXTURE_FRONT_CLEARANCE",
                    fixture,
                    front,
                    front_min,
                    front_target,
                    profile,
                    "front",
                )
            )

        if fixture.type == FixtureType.SHOWER:
            size_ok = (
                fixture.width_mm + 1 >= profile.clearances.shower_min_mm
                and fixture.depth_mm + 1 >= profile.clearances.shower_min_mm
            )
            results.append(
                _check(
                    "SHOWER_SIZE",
                    size_ok,
                    f"{fixture.id} is {fixture.width_mm:.0f} x {fixture.depth_mm:.0f} mm; "
                    f"minimum {profile.clearances.shower_min_mm:.0f} mm.",
                    "IPC 421.4",
                    measured=min(fixture.width_mm, fixture.depth_mm),
                    required=profile.clearances.shower_min_mm,
                    affected={"fixture_id": fixture.id},
                    fix_ids=["switch_layout"],
                )
            )

        if door_zone is not None:
            blocked = rects_overlap(fixture.bbox, door_zone)
            results.append(
                _check(
                    "DOOR_SWING",
                    not blocked,
                    f"{fixture.id} {'blocks' if blocked else 'clear of'} the door swing.",
                    "IPC 405.3.1; NBC 2016 Part 3",
                    affected={"fixture_id": fixture.id},
                    fix_ids=["switch_layout"],
                )
            )

        if stack_zone is not None:
            blocked = rects_overlap(fixture.bbox, stack_zone)
            results.append(
                _check(
                    "STACK_OBSTRUCTION",
                    not blocked,
                    f"{fixture.id} {'overlaps' if blocked else 'is clear of'} the stack/shaft.",
                    "Flowline geometry",
                    affected={"fixture_id": fixture.id},
                    fix_ids=["switch_layout"],
                )
            )

    fixtures = [fixture for fixture in design.fixtures if fixture.type != FixtureType.FLOOR_DRAIN]
    for index, fixture in enumerate(fixtures):
        for other in fixtures[index + 1 :]:
            center_distance = (
                (other.position.x - fixture.position.x) ** 2
                + (other.position.y - fixture.position.y) ** 2
            ) ** 0.5
            results.append(
                _check(
                    "FIXTURE_SPACING",
                    center_distance + 1 >= profile.clearances.center_spacing_mm,
                    f"{fixture.id}/{other.id} center spacing {center_distance:.0f} mm; "
                    f"minimum {profile.clearances.center_spacing_mm:.0f} mm.",
                    "IPC 405.3.1",
                    measured=round(center_distance, 1),
                    required=profile.clearances.center_spacing_mm,
                    affected={"fixtures": [fixture.id, other.id]},
                    fix_ids=["switch_layout"],
                )
            )
            results.append(
                _check(
                    "FIXTURE_OVERLAP",
                    not rects_overlap(inflate_bbox(fixture.bbox, 1), inflate_bbox(other.bbox, 1)),
                    f"{fixture.id}/{other.id} footprints do not overlap."
                    if not rects_overlap(fixture.bbox, other.bbox)
                    else f"{fixture.id}/{other.id} footprints overlap.",
                    "Flowline geometry",
                    affected={"fixtures": [fixture.id, other.id]},
                    fix_ids=["switch_layout"],
                )
            )
    return results


def _clearance_result(
    rule_id: str,
    fixture,
    measured: float,
    minimum: float,
    target: float,
    profile: RuleProfile,
    kind: str,
) -> ValidationResult:
    if measured + 1 < minimum:
        severity = Severity.ERROR
    elif measured + 1 < target:
        severity = Severity.WARNING
    else:
        severity = Severity.PASS
    message = (
        f"{fixture.id} {kind} clearance {measured:.0f} mm; "
        f"minimum {minimum:.0f} mm, target {target:.0f} mm."
    )
    return ValidationResult(
        rule_id=rule_id,
        severity=severity,
        message=message,
        source=profile.clearances.source,
        measured=round(measured, 1),
        required=minimum,
        affected={"fixture_id": fixture.id},
        fix_ids=["switch_layout"] if severity != Severity.PASS else [],
    )


def _pipe_results(building, room, design, profile: RuleProfile) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    if not design.pipes:
        results.append(
            _check(
                "PIPE_ROUTING",
                False,
                "No pipes have been routed.",
                "Flowline",
                fix_ids=["route_drainage"],
            )
        )
        return results

    for fixture in design.fixtures:
        connected = any(pipe.from_node == fixture.id for pipe in design.pipes)
        reaches = design.reaches_stack(fixture.id)
        results.append(
            _check(
                "PIPE_CONNECTIVITY",
                connected and reaches,
                f"{fixture.id} {'reaches' if reaches else 'does not reach'} the stack.",
                "Flowline connectivity",
                affected={"fixture_id": fixture.id},
                fix_ids=["route_drainage"],
            )
        )

    fixtures_by_id = {fixture.id: fixture for fixture in design.fixtures}
    door_zone = _door_zone(building, room)
    for pipe in design.pipes:
        source = fixtures_by_id.get(pipe.from_node)
        endpoint_ok = (
            source is not None
            and pipe.to_node == design.stack.id
            and len(pipe.points) >= 2
        )
        results.append(
            _check(
                "PIPE_ENDPOINTS",
                endpoint_ok,
                f"{pipe.id} endpoints {pipe.from_node} -> {pipe.to_node}.",
                "Flowline connectivity",
                affected={"pipe_id": pipe.id},
                fix_ids=["route_drainage"],
            )
        )

        if source is not None:
            expected = profile.pipe_for(source.type)
            results.append(
                _check(
                    "PIPE_DIAMETER",
                    abs(pipe.diameter_mm - expected.diameter_mm) < 0.1,
                    f"{pipe.id} diameter {pipe.diameter_mm:g} mm; required "
                    f"{expected.diameter_mm:g} mm for {source.type.value}.",
                    _pipe_source(profile),
                    measured=pipe.diameter_mm,
                    required=expected.diameter_mm,
                    affected={"pipe_id": pipe.id},
                    fix_ids=[f"size:{pipe.id}"],
                )
            )

        slope_rule = profile.slope_for(pipe.system)
        slope_ok = (
            pipe.slope is not None
            and slope_rule.min - 1e-9 <= pipe.slope <= slope_rule.max + 1e-9
        )
        results.append(
            _check(
                "PIPE_SLOPE",
                slope_ok,
                f"{pipe.id} slope {pipe.slope}; allowed {slope_rule.min} to {slope_rule.max}.",
                _slope_source(profile),
                measured=pipe.slope,
                required=f"{slope_rule.min}-{slope_rule.max}",
                affected={"pipe_id": pipe.id},
                fix_ids=[f"slope:{pipe.id}"],
            )
        )

        short_segments = [
            index
            for index in range(len(pipe.points) - 1)
            if _segment_length(pipe.points[index], pipe.points[index + 1]) < 5
        ]
        results.append(
            _check(
                "PIPE_MIN_SEGMENT",
                not short_segments,
                f"{pipe.id} has {len(short_segments)} segment(s) shorter than 5 mm.",
                "Flowline geometry",
                affected={"pipe_id": pipe.id},
                fix_ids=[f"reroute:{pipe.id}"],
                fail_severity=Severity.WARNING,
            )
        )

        outside = [
            point
            for point in pipe.points
            if not _inside_route_corridor(room, design.stack.position, point)
        ]
        results.append(
            _check(
                "PIPE_CONTAINMENT",
                not outside,
                f"{pipe.id} {'stays inside' if not outside else 'leaves'} the room/shaft corridor.",
                "Flowline geometry",
                measured=len(outside),
                required=0,
                affected={"pipe_id": pipe.id},
                fix_ids=[f"reroute:{pipe.id}"],
            )
        )

        crossed = _crossed_fixture(pipe, source.id if source else None, design)
        results.append(
            _check(
                "PIPE_FIXTURE_CROSSING",
                crossed is None,
                f"{pipe.id} {'crosses ' + crossed if crossed else 'avoids'} another fixture.",
                "Flowline geometry",
                affected={"pipe_id": pipe.id},
                fix_ids=[f"reroute:{pipe.id}"],
            )
        )

        if door_zone is not None:
            crosses_door = any(
                segment_intersects_bbox(
                    pipe.points[index], pipe.points[index + 1], door_zone
                )
                for index in range(len(pipe.points) - 1)
            )
            results.append(
                _check(
                    "PIPE_DOOR_CROSSING",
                    not crosses_door,
                    f"{pipe.id} {'crosses' if crosses_door else 'avoids'} the door swing; "
                    "coordinate the threshold if crossed.",
                    "Flowline coordination",
                    affected={"pipe_id": pipe.id},
                    fail_severity=Severity.WARNING,
                    fix_ids=[f"reroute:{pipe.id}"] if crosses_door else [],
                )
            )

        length = polyline_length(pipe.points)
        results.append(
            _check(
                "BRANCH_LENGTH",
                length <= profile.vent.max_branch_mm_warning,
                f"{pipe.id} branch length {length:.0f} mm; vent warning threshold "
                f"{profile.vent.max_branch_mm_warning:.0f} mm.",
                profile.vent.source,
                measured=round(length, 1),
                required=profile.vent.max_branch_mm_warning,
                affected={"pipe_id": pipe.id},
                fail_severity=Severity.WARNING,
            )
        )

    results.append(
        _check(
            "STACK_DIAMETER",
            design.stack.diameter_mm + 0.1 >= profile.stack.min_diameter_mm,
            f"Stack {design.stack.id} diameter {design.stack.diameter_mm:g} mm; minimum "
            f"{profile.stack.min_diameter_mm:g} mm.",
            profile.stack.source,
            measured=design.stack.diameter_mm,
            required=profile.stack.min_diameter_mm,
            affected={"stack_id": design.stack.id},
        )
    )

    total_units = sum(profile.fixture_unit(fixture.type) for fixture in design.fixtures)
    results.append(
        _check(
            "FIXTURE_UNITS",
            True,
            f"Total fixture load {total_units:g} DFU (informational; stack sizing is a later check).",
            "IPC 709.1",
            measured=total_units,
            required="informational",
            affected={},
        )
    )
    return results


def _check(
    rule_id: str,
    ok: bool,
    message: str,
    source: str,
    measured=None,
    required=None,
    affected: dict | None = None,
    fix_ids: list[str] | None = None,
    fail_severity: Severity = Severity.ERROR,
) -> ValidationResult:
    return ValidationResult(
        rule_id=rule_id,
        severity=Severity.PASS if ok else fail_severity,
        message=message,
        source=source,
        measured=measured,
        required=required,
        affected=affected or {},
        fix_ids=[] if ok else (fix_ids or []),
    )


def _pipe_source(profile: RuleProfile) -> str:
    for source in profile.sources:
        if profile.region.lower().startswith("india") and (
            "Part 9" in source or "1742" in source
        ):
            return source
        if not profile.region.lower().startswith("india") and "Chapter 7" in source:
            return source
    return profile.name


def _slope_source(profile: RuleProfile) -> str:
    for source in profile.sources:
        if "1742" in source or "Chapter 7" in source or "drainage" in source.lower():
            return source
    return profile.name


def _inside_route_corridor(room, stack: Point, point: Point) -> bool:
    if room.contains(point):
        return True
    nearest = Point(
        x=min(max(stack.x, room.bbox.minx), room.bbox.maxx),
        y=min(max(stack.y, room.bbox.miny), room.bbox.maxy),
    )
    return (
        min(nearest.x, stack.x) - 300 <= point.x <= max(nearest.x, stack.x) + 300
        and min(nearest.y, stack.y) - 300 <= point.y <= max(nearest.y, stack.y) + 300
    )


def _crossed_fixture(pipe, source_id: str | None, design: Design) -> str | None:
    for fixture in design.fixtures:
        if fixture.id == source_id:
            continue
        box = inflate_bbox(fixture.bbox, 10)
        for index in range(len(pipe.points) - 1):
            if segment_intersects_bbox(pipe.points[index], pipe.points[index + 1], box):
                return fixture.id
    return None


def _segment_length(start: Point, end: Point) -> float:
    return ((end.x - start.x) ** 2 + (end.y - start.y) ** 2) ** 0.5
