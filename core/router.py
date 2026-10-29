from __future__ import annotations

import heapq
from math import ceil, floor

from core.geometry import BBox, Point, dedupe_collinear, inflate_bbox
from core.layout import _door_zone
from core.models import Building, Design, Pipe, Room
from core.rules.engine import RuleProfile

CELL_MM = 50.0
MARGIN_MM = 300.0
BEND_PENALTY = 0.8
MAX_GRID_CELLS = 150_000
DIRECTIONS = ((1, 0), (-1, 0), (0, 1), (0, -1))


class RouteError(ValueError):
    """No valid pipe route exists for a fixture."""


def route_design(building: Building, design: Design, profile: RuleProfile) -> list[Pipe]:
    room = building.room(design.room_id)
    door_zone = _door_zone(building, room)
    pipes: list[Pipe] = []
    for index, fixture in enumerate(design.fixtures, start=1):
        obstacles = [
            inflate_bbox(other.bbox, 50)
            for other in design.fixtures
            if other.id != fixture.id
        ]
        start = fixture.drain_point(design.stack.position)
        points = _route_one(
            room,
            start,
            design.stack.position,
            obstacles,
            door_zone,
            fixture.id,
        )
        rule = profile.pipe_for(fixture.type)
        slope = profile.slope_for(rule.system).default
        pipes.append(
            Pipe(
                id=f"P-{index:02d}",
                system=rule.system,
                diameter_mm=rule.diameter_mm,
                points=points,
                slope=slope,
                from_node=fixture.id,
                to_node=design.stack.id,
            )
        )
    design.pipes = pipes
    return pipes


def _route_one(
    room: Room,
    start: Point,
    end: Point,
    obstacles: list[BBox],
    door_zone: BBox | None,
    fixture_id: str,
) -> list[Point]:
    for block_door, inflation in ((True, 50.0), (False, 50.0), (False, 0.0)):
        adjusted = [inflate_bbox(obstacle, inflation - 50.0) for obstacle in obstacles]
        route = _try_route(room, start, end, adjusted, door_zone, block_door)
        if route is not None:
            return route
    raise RouteError(f"{fixture_id}: no route to the stack inside the room or shaft corridor.")


def _try_route(
    room: Room,
    start: Point,
    end: Point,
    obstacles: list[BBox],
    door_zone: BBox | None,
    block_door: bool,
) -> list[Point] | None:
    bounds, corridor = _grid_bounds(room, start, end)
    width = int(round(bounds.width / CELL_MM))
    height = int(round(bounds.height / CELL_MM))
    if width <= 0 or height <= 0 or width * height > MAX_GRID_CELLS:
        return None

    free: set[tuple[int, int]] = set()
    for gx in range(width):
        for gy in range(height):
            point = _cell_point(gx, gy, bounds)
            if not _inside(room, corridor, point):
                continue
            if block_door and door_zone is not None and door_zone.contains(point):
                continue
            if any(obstacle.contains(point) for obstacle in obstacles):
                continue
            free.add((gx, gy))

    start_cell = _nearest_free(_cell_index(start, bounds), free, width, height)
    end_cell = _nearest_free(_cell_index(end, bounds), free, width, height)
    if start_cell is None or end_cell is None:
        return None

    cells = _astar(start_cell, end_cell, free, width, height)
    if cells is None:
        return None

    centers = [_cell_point(gx, gy, bounds) for gx, gy in cells]
    points = _connect(start, centers, end)
    points = _drop_backtracks(points)
    points = dedupe_collinear(points)
    if len(points) < 2:
        points = [start, end]
    return points


def _grid_bounds(room: Room, start: Point, end: Point) -> tuple[BBox, BBox | None]:
    minx = floor((min(room.bbox.minx, start.x, end.x) - MARGIN_MM) / CELL_MM) * CELL_MM
    miny = floor((min(room.bbox.miny, start.y, end.y) - MARGIN_MM) / CELL_MM) * CELL_MM
    maxx = ceil((max(room.bbox.maxx, start.x, end.x) + MARGIN_MM) / CELL_MM) * CELL_MM
    maxy = ceil((max(room.bbox.maxy, start.y, end.y) + MARGIN_MM) / CELL_MM) * CELL_MM
    bounds = BBox(minx, miny, maxx, maxy)

    corridor: BBox | None = None
    if not room.bbox.contains(end, tolerance=1):
        nearest = Point(
            x=min(max(end.x, room.bbox.minx), room.bbox.maxx),
            y=min(max(end.y, room.bbox.miny), room.bbox.maxy),
        )
        corridor = BBox(
            min(nearest.x, end.x) - 200,
            min(nearest.y, end.y) - 200,
            max(nearest.x, end.x) + 200,
            max(nearest.y, end.y) + 200,
        )
    return bounds, corridor


def _inside(room: Room, corridor: BBox | None, point: Point) -> bool:
    if room.contains(point):
        return True
    return corridor is not None and corridor.contains(point)


def _cell_index(point: Point, bounds: BBox) -> tuple[int, int]:
    return (
        int((point.x - bounds.minx) // CELL_MM),
        int((point.y - bounds.miny) // CELL_MM),
    )


def _cell_point(gx: int, gy: int, bounds: BBox) -> Point:
    return Point(
        x=bounds.minx + (gx + 0.5) * CELL_MM,
        y=bounds.miny + (gy + 0.5) * CELL_MM,
    )


def _nearest_free(
    cell: tuple[int, int],
    free: set[tuple[int, int]],
    width: int,
    height: int,
    max_radius: int = 12,
) -> tuple[int, int] | None:
    if cell in free:
        return cell
    gx, gy = cell
    for radius in range(1, max_radius + 1):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if max(abs(dx), abs(dy)) != radius:
                    continue
                candidate = (gx + dx, gy + dy)
                if 0 <= candidate[0] < width and 0 <= candidate[1] < height:
                    if candidate in free:
                        return candidate
    return None


def _astar(
    start: tuple[int, int],
    goal: tuple[int, int],
    free: set[tuple[int, int]],
    width: int,
    height: int,
) -> list[tuple[int, int]] | None:
    def heuristic(cell: tuple[int, int]) -> float:
        return abs(cell[0] - goal[0]) + abs(cell[1] - goal[1])

    start_state = (start[0], start[1], -1)
    open_heap: list[tuple[float, float, int, int, int]] = [
        (heuristic(start), 0.0, start[0], start[1], -1)
    ]
    best: dict[tuple[int, int, int], float] = {start_state: 0.0}
    came: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    closed: set[tuple[int, int, int]] = set()

    while open_heap:
        _, cost, gx, gy, direction = heapq.heappop(open_heap)
        state = (gx, gy, direction)
        if state in closed:
            continue
        closed.add(state)
        if (gx, gy) == goal:
            return _reconstruct(came, state)

        for new_direction, (dx, dy) in enumerate(DIRECTIONS):
            nx, ny = gx + dx, gy + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if (nx, ny) not in free:
                continue
            step = 1.0
            if direction != -1 and direction != new_direction:
                step += BEND_PENALTY
            new_cost = cost + step
            new_state = (nx, ny, new_direction)
            if new_cost + 1e-9 >= best.get(new_state, float("inf")):
                continue
            best[new_state] = new_cost
            came[new_state] = state
            heapq.heappush(
                open_heap,
                (new_cost + heuristic((nx, ny)), new_cost, nx, ny, new_direction),
            )
    return None


def _reconstruct(
    came: dict[tuple[int, int, int], tuple[int, int, int]],
    state: tuple[int, int, int],
) -> list[tuple[int, int]]:
    cells = [(state[0], state[1])]
    while state in came:
        state = came[state]
        cells.append((state[0], state[1]))
    cells.reverse()
    return cells


def _connect(start: Point, centers: list[Point], end: Point) -> list[Point]:
    points: list[Point] = [start]
    for center in centers:
        points.append(center)
    points.append(end)
    orthogonal: list[Point] = [points[0]]
    for target in points[1:]:
        previous = orthogonal[-1]
        if previous.x != target.x and previous.y != target.y:
            orthogonal.append(Point(x=target.x, y=previous.y))
        orthogonal.append(target)
    return orthogonal


def _drop_backtracks(points: list[Point]) -> list[Point]:
    cleaned: list[Point] = []
    for point in points:
        if len(cleaned) >= 2:
            first, middle = cleaned[-2], cleaned[-1]
            horizontal = first.y == middle.y == point.y and (
                (middle.x - first.x) * (point.x - middle.x) < 0
            )
            vertical = first.x == middle.x == point.x and (
                (middle.y - first.y) * (point.y - middle.y) < 0
            )
            if horizontal or vertical:
                cleaned.pop()
        if cleaned and cleaned[-1] == point:
            continue
        cleaned.append(point)
    return cleaned
