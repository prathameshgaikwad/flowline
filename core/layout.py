from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations, product
from math import hypot

from core.fixtures import spec_for
from core.geometry import BBox, Point, inflate_bbox, manhattan, rects_overlap
from core.models import Building, Fixture, FixtureType, LayoutCandidate, Room

MIN_CENTER_SPACING_MM = 762.0
DOOR_DEPTH_MM = 900.0
WALL_IDS = ("bottom", "right", "top", "left")


@dataclass(frozen=True)
class Wall:
    id: str
    start: Point
    end: Point
    inward: tuple[float, float]
    rotation: float
    length: float

    @property
    def unit(self) -> tuple[float, float]:
        if self.id == "bottom":
            return (1.0, 0.0)
        if self.id == "right":
            return (0.0, 1.0)
        if self.id == "top":
            return (-1.0, 0.0)
        return (0.0, -1.0)


def generate_layouts(
    building: Building,
    room_id: str,
    fixture_types: list[FixtureType],
    stack: Point,
    max_results: int = 5,
) -> list[LayoutCandidate]:
    room = building.room(room_id)
    if not room.is_closed:
        return []
    types = list(dict.fromkeys(fixture_types))
    if not types:
        return []

    box = room.bbox
    walls = _walls(box)
    door_zone = _door_zone(building, room)
    stack_zone = _stack_zone(building, room, stack)

    seen: dict[tuple, LayoutCandidate] = {}
    for pattern, groups in _pattern_variants(walls, types):
        wall_map = {wall.id: wall for wall in walls}
        for alignments in _alignment_product(len(groups)):
            fixtures: list[Fixture] = []
            failed = False
            for (wall_id, group_types), alignment in zip(groups, alignments):
                placed = _place_group(
                    wall_map[wall_id], group_types, alignment, room, door_zone
                )
                if placed is None:
                    failed = True
                    break
                fixtures.extend(placed)
            if failed:
                continue
            violations = _violations(room, fixtures, door_zone, stack_zone, stack)
            score, hint = _score(pattern, fixtures, stack, door_zone, violations, room)
            candidate = LayoutCandidate(
                id="",
                pattern=pattern,
                fixtures=fixtures,
                score=score,
                violations=violations,
                rationale_hint=hint,
            )
            signature = _signature(fixtures)
            existing = seen.get(signature)
            if existing is None or candidate.score > existing.score:
                seen[signature] = candidate

    ranked = sorted(seen.values(), key=lambda item: (-item.score, _signature(item.fixtures)))
    selected = _diverse(ranked, max_results)
    for index, candidate in enumerate(selected, start=1):
        candidate.id = f"C-{index:02d}"
    return selected


def _diverse(ranked: list[LayoutCandidate], max_results: int) -> list[LayoutCandidate]:
    valid = [candidate for candidate in ranked if not candidate.violations]
    pool = valid or ranked

    by_pattern: dict[str, list[LayoutCandidate]] = {}
    for candidate in pool:
        by_pattern.setdefault(candidate.pattern, []).append(candidate)
    order = sorted(by_pattern, key=lambda pattern: -by_pattern[pattern][0].score)
    selected: list[LayoutCandidate] = []
    depth = 0
    while len(selected) < max_results:
        added = False
        for pattern in order:
            candidates = by_pattern[pattern]
            if depth < len(candidates):
                selected.append(candidates[depth])
                added = True
                if len(selected) >= max_results:
                    break
        if not added:
            break
        depth += 1

    if len(selected) < max_results:
        for candidate in ranked:
            if candidate not in selected:
                selected.append(candidate)
            if len(selected) >= max_results:
                break

    selected = sorted(selected, key=lambda item: (-item.score, _signature(item.fixtures)))
    return selected[:max_results]


def _walls(box: BBox) -> list[Wall]:
    return [
        Wall("bottom", Point(x=box.minx, y=box.miny), Point(x=box.maxx, y=box.miny), (0, 1), 0.0, box.width),
        Wall("right", Point(x=box.maxx, y=box.miny), Point(x=box.maxx, y=box.maxy), (-1, 0), 90.0, box.height),
        Wall("top", Point(x=box.maxx, y=box.maxy), Point(x=box.minx, y=box.maxy), (0, -1), 180.0, box.width),
        Wall("left", Point(x=box.minx, y=box.maxy), Point(x=box.minx, y=box.miny), (1, 0), 270.0, box.height),
    ]


def _pattern_variants(walls: list[Wall], types: list[FixtureType]):
    wall_map = {wall.id: wall for wall in walls}
    ids = list(WALL_IDS)
    orders = list(permutations(types))
    others = [fixture_type for fixture_type in types if fixture_type != FixtureType.WC]

    for wall_id in ids:
        for order in orders:
            yield "wet_wall", [(wall_id, list(order))]

    if FixtureType.WC in types:
        for wall_id in ids:
            for neighbor in _adjacent(wall_id):
                for order in permutations(others):
                    yield "split", [(wall_id, [FixtureType.WC]), (neighbor, list(order))]

    if FixtureType.SHOWER in types:
        rest = [fixture_type for fixture_type in types if fixture_type != FixtureType.SHOWER]
        for wall_id in ids:
            for neighbor in _adjacent(wall_id):
                for other_wall in ids:
                    if other_wall in (wall_id, neighbor):
                        continue
                    yield "corner_shower", [
                        (wall_id, [FixtureType.SHOWER]),
                        (neighbor, rest[:1]),
                        (other_wall, rest[1:2]),
                    ]

    if FixtureType.SHOWER in types and FixtureType.WC in types:
        rest = [fixture_type for fixture_type in types if fixture_type not in (FixtureType.SHOWER, FixtureType.WC)]
        for wall_id in ids:
            opposite = _opposite(wall_id)
            for order in permutations([FixtureType.WC, *rest]):
                yield "opposite", [
                    (wall_id, list(order)),
                    (opposite, [FixtureType.SHOWER]),
                ]

    longest = sorted(ids, key=lambda wall_id: wall_map[wall_id].length, reverse=True)[:2]
    for wall_id in longest:
        for order in orders:
            yield "long_wall", [(wall_id, list(order))]


def _alignment_product(count: int):
    options = ("start", "end", "center")
    for values in product(options, repeat=count):
        yield values


def _place_group(
    wall: Wall,
    types: list[FixtureType],
    alignment: str,
    room: Room,
    door_zone: BBox | None,
) -> list[Fixture] | None:
    if not types:
        return None
    specs = [spec_for(fixture_type) for fixture_type in types]
    centers: list[float] = []
    cursor = 0.0
    previous_center: float | None = None
    previous_width: float | None = None
    for spec in specs:
        if previous_center is None:
            center = cursor + spec.width_mm / 2
        else:
            center = max(
                cursor + spec.width_mm / 2,
                previous_center + MIN_CENTER_SPACING_MM - spec.width_mm / 2,
                previous_center + previous_width / 2 + spec.width_mm / 2 + 50,
            )
        centers.append(center)
        cursor = center + spec.width_mm / 2
        previous_center = center
        previous_width = spec.width_mm

    total = centers[-1] + specs[-1].width_mm / 2
    first_center = centers[0]
    min_offset = max(0.0, specs[0].min_side_mm - first_center)
    max_offset = wall.length - total - max(
        0.0, specs[-1].min_side_mm - specs[-1].width_mm / 2
    )
    if max_offset < min_offset:
        return None
    if alignment == "start":
        offset = min_offset
    elif alignment == "end":
        offset = max_offset
    else:
        offset = min(max((wall.length - total) / 2, min_offset), max_offset)

    fixtures: list[Fixture] = []
    for index, spec in enumerate(specs):
        center_along = offset + centers[index]
        position = Point(
            x=wall.start.x + wall.unit[0] * center_along + wall.inward[0] * spec.depth_mm / 2,
            y=wall.start.y + wall.unit[1] * center_along + wall.inward[1] * spec.depth_mm / 2,
        )
        fixture = Fixture(
            id=f"{spec.label}-{wall.id[0].upper()}{index + 1}",
            type=spec.type,
            position=position,
            rotation_deg=wall.rotation,
            width_mm=spec.width_mm,
            depth_mm=spec.depth_mm,
            room_id=room.id,
            wall_id=wall.id,
        )
        filters = _fixture_violations(fixture, room, door_zone)
        if filters:
            return None
        fixtures.append(fixture)
    return fixtures


def _fixture_violations(
    fixture: Fixture, room: Room, door_zone: BBox | None
) -> list[str]:
    violations: list[str] = []
    box = fixture.bbox
    if not all(
        room.contains(Point(x=x, y=y))
        for x, y in (
            (box.minx, box.miny),
            (box.maxx, box.miny),
            (box.maxx, box.maxy),
            (box.minx, box.maxy),
        )
    ):
        violations.append("fixture outside room")
    if door_zone is not None and rects_overlap(box, door_zone):
        violations.append("fixture in door swing")
    return violations


def _violations(
    room: Room,
    fixtures: list[Fixture],
    door_zone: BBox | None,
    stack_zone: BBox | None,
    stack: Point,
) -> list[str]:
    violations: list[str] = []
    for fixture in fixtures:
        spec = spec_for(fixture.type)
        box = fixture.bbox
        if not all(
            room.contains(Point(x=x, y=y))
            for x, y in (
                (box.minx, box.miny),
                (box.maxx, box.miny),
                (box.maxx, box.maxy),
                (box.minx, box.maxy),
            )
        ):
            violations.append(f"{fixture.id}: outside room")
        side_distance = _side_distance(fixture, room.bbox)
        if side_distance + 1 < spec.min_side_mm:
            violations.append(f"{fixture.id}: side clearance {side_distance:.0f}mm")
        front_distance = _front_distance(fixture, room.bbox)
        if front_distance + 1 < spec.min_front_mm:
            violations.append(f"{fixture.id}: front clearance {front_distance:.0f}mm")
        front_zone = _front_zone(fixture, spec.min_front_mm)
        for other in fixtures:
            if other.id == fixture.id:
                continue
            if rects_overlap(inflate_bbox(other.bbox, 25), front_zone):
                violations.append(f"{fixture.id}: front blocked by {other.id}")
        if door_zone is not None and rects_overlap(box, door_zone):
            violations.append(f"{fixture.id}: door swing")
        if stack_zone is not None and rects_overlap(inflate_bbox(box, 25), stack_zone):
            violations.append(f"{fixture.id}: stack/shaft obstruction")
        if fixture.type == FixtureType.SHOWER and (
            fixture.width_mm < 762 or fixture.depth_mm < 762
        ):
            violations.append(f"{fixture.id}: shower smaller than 762mm")

    for index, fixture in enumerate(fixtures):
        if fixture.type == FixtureType.FLOOR_DRAIN:
            continue
        for other in fixtures[index + 1 :]:
            if other.type == FixtureType.FLOOR_DRAIN:
                continue
            center_distance = hypot(
                other.position.x - fixture.position.x, other.position.y - fixture.position.y
            )
            if center_distance + 1 < MIN_CENTER_SPACING_MM:
                violations.append(
                    f"{fixture.id}/{other.id}: center spacing {center_distance:.0f}mm"
                )
    return list(dict.fromkeys(violations))


def _score(
    pattern: str,
    fixtures: list[Fixture],
    stack: Point,
    door_zone: BBox | None,
    violations: list[str],
    room: Room,
) -> tuple[float, str]:
    route = sum(manhattan(fixture.drain_point(stack), stack) for fixture in fixtures)
    bends = sum(
        1
        for fixture in fixtures
        if abs(fixture.drain_point(stack).x - stack.x) > 1
        and abs(fixture.drain_point(stack).y - stack.y) > 1
    )
    comfort = 0.0
    for fixture in fixtures:
        spec = spec_for(fixture.type)
        comfort += max(0.0, _front_distance(fixture, room.bbox) - spec.min_front_mm) * 0.05
        comfort += max(0.0, _side_distance(fixture, room.bbox) - spec.min_side_mm) * 0.05
    door_bonus = 0.0
    door = _door_center(door_zone)
    shower = next((f for f in fixtures if f.type == FixtureType.SHOWER), None)
    if door and shower:
        door_bonus = min(500.0, hypot(shower.position.x - door.x, shower.position.y - door.y)) * 0.05
    wc = next((f for f in fixtures if f.type == FixtureType.WC), None)
    wc_bonus = 0.0
    if wc:
        wc_bonus = max(0.0, 500.0 - hypot(wc.position.x - stack.x, wc.position.y - stack.y)) * 0.08
    pattern_bonus = {
        "wet_wall": 30.0,
        "split": 20.0,
        "corner_shower": 25.0,
        "opposite": 10.0,
        "long_wall": 5.0,
    }.get(pattern, 0.0)
    base = 1000.0 if not violations else -1000.0 * len(violations)
    score = (
        base
        + 300.0
        - route / 120.0
        - bends * 8.0
        + comfort
        + door_bonus
        + wc_bonus
        + pattern_bonus
    )
    hints = {
        "wet_wall": "All fixtures share the wet wall; shortest branch runs.",
        "split": "WC on the stack wall; basin and shower grouped on an adjacent wall.",
        "corner_shower": "Shower in a corner; WC kept near the stack.",
        "opposite": "Wet fixtures split across opposite walls.",
        "long_wall": "Fixtures in line along the longest wall.",
    }
    hint = hints.get(pattern, "Generated layout.")
    if violations:
        hint = "Best-effort layout; " + "; ".join(violations[:3])
    return score, hint


def _side_distance(fixture: Fixture, box: BBox) -> float:
    if int(round(fixture.rotation_deg)) % 180 == 0:
        return min(fixture.position.x - box.minx, box.maxx - fixture.position.x)
    return min(fixture.position.y - box.miny, box.maxy - fixture.position.y)


def _front_distance(fixture: Fixture, box: BBox) -> float:
    rotation = int(round(fixture.rotation_deg)) % 360
    if rotation == 0:
        return box.maxy - (fixture.position.y + fixture.depth_mm / 2)
    if rotation == 180:
        return (fixture.position.y - fixture.depth_mm / 2) - box.miny
    if rotation == 90:
        return (fixture.position.x - fixture.depth_mm / 2) - box.minx
    return box.maxx - (fixture.position.x + fixture.depth_mm / 2)


def _front_zone(fixture: Fixture, depth: float) -> BBox:
    box = fixture.bbox
    rotation = int(round(fixture.rotation_deg)) % 360
    if rotation == 0:
        return BBox(box.minx, box.maxy, box.maxx, box.maxy + depth)
    if rotation == 180:
        return BBox(box.minx, box.miny - depth, box.maxx, box.miny)
    if rotation == 90:
        return BBox(box.minx - depth, box.miny, box.minx, box.maxy)
    return BBox(box.maxx, box.miny, box.maxx + depth, box.maxy)


def _door_zone(building: Building, room: Room) -> BBox | None:
    if not building.doors:
        return None
    box = room.bbox
    door = min(
        building.doors,
        key=lambda item: hypot(
            item.position.x - box.center.x, item.position.y - box.center.y
        ),
    )
    width = max(door.width_mm, 600.0)
    distances = {
        "bottom": abs(door.position.y - box.miny),
        "top": abs(door.position.y - box.maxy),
        "left": abs(door.position.x - box.minx),
        "right": abs(door.position.x - box.maxx),
    }
    wall = min(distances, key=distances.get)
    if distances[wall] > 500:
        return None
    if wall == "bottom":
        return BBox(
            max(box.minx, door.position.x - width / 2),
            box.miny,
            min(box.maxx, door.position.x + width / 2),
            box.miny + width,
        )
    if wall == "top":
        return BBox(
            max(box.minx, door.position.x - width / 2),
            box.maxy - width,
            min(box.maxx, door.position.x + width / 2),
            box.maxy,
        )
    if wall == "left":
        return BBox(
            box.minx,
            max(box.miny, door.position.y - width / 2),
            box.minx + width,
            min(box.maxy, door.position.y + width / 2),
        )
    return BBox(
        box.maxx - width,
        max(box.miny, door.position.y - width / 2),
        box.maxx,
        min(box.maxy, door.position.y + width / 2),
    )


def _stack_zone(building: Building, room: Room, stack: Point) -> BBox | None:
    for shaft in building.shafts:
        if hypot(shaft.position.x - stack.x, shaft.position.y - stack.y) < 200:
            return inflate_bbox(shaft.bbox, 50)
    if room.bbox.contains(stack):
        return BBox(stack.x - 150, stack.y - 150, stack.x + 150, stack.y + 150)
    return None


def _door_center(zone: BBox | None) -> Point | None:
    return zone.center if zone is not None else None


def _adjacent(wall_id: str) -> tuple[str, str]:
    index = WALL_IDS.index(wall_id)
    return WALL_IDS[(index - 1) % 4], WALL_IDS[(index + 1) % 4]


def _opposite(wall_id: str) -> str:
    return WALL_IDS[(WALL_IDS.index(wall_id) + 2) % 4]


def _signature(fixtures: list[Fixture]) -> tuple:
    return tuple(
        sorted(
            (fixture.type.value, round(fixture.position.x / 50), round(fixture.position.y / 50))
            for fixture in fixtures
        )
    )
