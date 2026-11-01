from __future__ import annotations

from core.consolidated import (
    nearest_water_source,
    room_design_view,
    water_sources_for_building,
)
from core.fixtures import connections_for
from core.geometry import Point, distance, inflate_bbox
from core.layout import _door_zone
from core.models import (
    Building,
    Design,
    FixtureType,
    Pipe,
    PlumbingItem,
    PlumbingItemType,
    Shaft,
    ShaftService,
    SupplyPipe,
    SupplySystem,
    VentStack,
    WaterSource,
)
from core.router import RouteError, route_path
from core.rules.engine import RuleProfile

VENT_OFFSET_MM = 420.0
SOURCE_OFFSET_MM = 650.0


def build_plumbing(building: Building, design: Design, profile: RuleProfile) -> Design:
    design.vent_stacks = _vent_stacks(building, design)
    design.vent_stack = design.vent_stacks[0] if design.vent_stacks else None
    design.water_sources = water_sources_for_building(building)
    if not design.water_sources:
        design.water_sources = [_water_source(design)]
    _assign_water_sources(building, design)
    design.water_source = (
        design.water_source_for_room(design.room_id)
        or design.water_sources[0]
    )
    if design.room_plans:
        vent_pipes: list[Pipe] = []
        supply_pipes: list[SupplyPipe] = []
        for plan in design.room_plans:
            view = room_design_view(design, plan.room_id)
            view.vent_stack = design.vent_stack_for_room(plan.room_id)
            view.water_source = design.water_source_for_room(plan.room_id)
            try:
                room_vents = route_vent(building, view, profile)
            except RouteError as exc:
                design.route_failures.append(f"{plan.room_id}: vent: {exc}")
            else:
                for pipe in room_vents:
                    pipe.room_id = plan.room_id
                    vent_pipes.append(pipe)
            try:
                room_supplies = route_supply(building, view, profile)
            except RouteError as exc:
                design.route_failures.append(f"{plan.room_id}: supply: {exc}")
            else:
                for pipe in room_supplies:
                    pipe.room_id = plan.room_id
                    supply_pipes.append(pipe)
        design.vent_pipes = _renumber_vent(vent_pipes)
        design.supply_pipes = _renumber_supply(supply_pipes)
    else:
        design.vent_pipes = route_vent(building, design, profile)
        design.supply_pipes = route_supply(building, design, profile)
    design.plumbing_items = _items(design)
    return design


def _assign_water_sources(building: Building, design: Design) -> None:
    source_ids = {source.id for source in design.water_sources}
    for plan in design.room_plans:
        if plan.water_source_id in source_ids:
            continue
        try:
            room = building.room(plan.room_id)
        except KeyError:
            plan.water_source_id = None
            continue
        source = nearest_water_source(room, design.water_sources)
        plan.water_source_id = source.id if source is not None else None


def route_vent(
    building: Building, design: Design, profile: RuleProfile
) -> list[Pipe]:
    room = building.room(design.room_id)
    vent_stack = design.vent_stack or _vent_stack(design, building)
    door_zone = _door_zone(building, room)
    pipes: list[Pipe] = []
    for index, fixture in enumerate(design.fixtures, start=1):
        connections = connections_for(fixture)
        if connections.vent is None:
            continue
        obstacles = [
            inflate_bbox(other.bbox, 50)
            for other in design.fixtures
            if other.id != fixture.id
        ]
        points = route_path(
            room,
            connections.vent,
            vent_stack.position,
            obstacles,
            door_zone,
            f"vent:{fixture.id}",
        )
        pipes.append(
            Pipe(
                id=f"V-{index:02d}",
                system="VENT",
                diameter_mm=profile.vent.min_diameter_mm,
                points=points,
                slope=0.0,
                from_node=fixture.id,
                to_node=vent_stack.id,
                room_id=design.room_id,
            )
        )
    return pipes


def route_supply(
    building: Building, design: Design, profile: RuleProfile
) -> list[SupplyPipe]:
    room = building.room(design.room_id)
    source = design.water_source or _water_source(design)
    door_zone = _door_zone(building, room)
    pipes: list[SupplyPipe] = []
    cold_index = 0
    hot_index = 0
    for fixture in design.fixtures:
        connections = connections_for(fixture)
        obstacles = [
            inflate_bbox(other.bbox, 50)
            for other in design.fixtures
            if other.id != fixture.id
        ]
        if connections.cold is not None:
            cold_index += 1
            diameter = profile.supply.cold_fixture_mm.get(
                fixture.type.value, profile.supply.cold_main_mm
            )
            points = _route_from_source(
                room,
                source.position,
                connections.cold,
                obstacles,
                door_zone,
                f"cold:{fixture.id}",
            )
            pipes.append(
                SupplyPipe(
                    id=f"CW-{cold_index:02d}",
                    system=SupplySystem.COLD,
                    diameter_mm=diameter,
                    points=points,
                    from_node=source.id,
                    to_node=fixture.id,
                    material=source.material,
                    room_id=design.room_id,
                )
            )
        if connections.hot is not None:
            hot_index += 1
            diameter = profile.supply.hot_fixture_mm.get(
                fixture.type.value, profile.supply.hot_main_mm
            )
            hot_source = Point(x=source.position.x + 160, y=source.position.y + 120)
            points = _route_from_source(
                room,
                hot_source,
                connections.hot,
                obstacles,
                door_zone,
                f"hot:{fixture.id}",
            )
            pipes.append(
                SupplyPipe(
                    id=f"HW-{hot_index:02d}",
                    system=SupplySystem.HOT,
                    diameter_mm=diameter,
                    points=points,
                    from_node=source.id,
                    to_node=fixture.id,
                    material=source.material,
                    room_id=design.room_id,
                )
            )
    return pipes


def _route_from_source(
    room,
    source: Point,
    target: Point,
    obstacles,
    door_zone,
    label: str,
) -> list[Point]:
    if room.contains(source):
        return route_path(room, source, target, obstacles, door_zone, label)
    entry = Point(
        x=min(max(source.x, room.bbox.minx), room.bbox.maxx),
        y=min(max(source.y, room.bbox.miny), room.bbox.maxy),
    )
    points = route_path(room, entry, target, obstacles, door_zone, label)
    if points and points[0] == source:
        return points
    return [source, *points]


def _vent_stacks(building: Building, design: Design) -> list[VentStack]:
    stacks = list(design.stacks) or [design.stack]
    if design.stack.id not in {stack.id for stack in stacks}:
        stacks.insert(0, design.stack)
    result: list[VentStack] = []
    for index, stack in enumerate(stacks, start=1):
        shaft = _vent_shaft_for_stack(building, stack)
        if shaft is not None:
            position = _port_point(shaft, -0.15, 0.15)
            shaft_id = shaft.id
        else:
            position = Point(
                x=stack.position.x + VENT_OFFSET_MM,
                y=stack.position.y,
            )
            shaft_id = None
        result.append(
            VentStack(
                id=f"VS{index}",
                stack_id=stack.id,
                position=position,
                diameter_mm=50.0,
                shaft_id=shaft_id,
            )
        )
    return result


def _renumber_vent(pipes: list[Pipe]) -> list[Pipe]:
    for index, pipe in enumerate(pipes, start=1):
        pipe.id = f"V-{index:02d}"
    return pipes


def _renumber_supply(pipes: list[SupplyPipe]) -> list[SupplyPipe]:
    cold = 0
    hot = 0
    for pipe in pipes:
        if pipe.system == SupplySystem.HOT:
            hot += 1
            pipe.id = f"HW-{hot:02d}"
        else:
            cold += 1
            pipe.id = f"CW-{cold:02d}"
    return pipes


def _vent_stack(design: Design, building: Building | None = None) -> VentStack:
    if building is not None:
        stacks = _vent_stacks(building, design)
        if stacks:
            return stacks[0]
    return VentStack(
        id="VS1",
        stack_id=design.stack.id,
        position=Point(
            x=design.stack.position.x + VENT_OFFSET_MM,
            y=design.stack.position.y,
        ),
        diameter_mm=50.0,
    )


def _water_source(design: Design) -> WaterSource:
    return WaterSource(
        id="WS1",
        position=Point(
            x=design.stack.position.x - SOURCE_OFFSET_MM,
            y=design.stack.position.y,
        ),
        pressure_kpa=300.0,
        cold_diameter_mm=25.0,
        hot_diameter_mm=20.0,
        heater=True,
        heater_capacity_l=50.0,
        heater_fuel="electric",
        material="CPVC",
        shaft_id=design.stack.shaft_id,
    )


def _shaft_for_stack(building: Building, stack) -> Shaft | None:
    if stack.shaft_id:
        for shaft in building.shafts:
            if shaft.id == stack.shaft_id:
                return shaft
    for shaft in building.shafts:
        if abs(shaft.position.x - stack.position.x) <= 200 and abs(
            shaft.position.y - stack.position.y
        ) <= 200:
            return shaft
    return None


def _vent_shaft_for_stack(building: Building, stack) -> Shaft | None:
    shaft = _shaft_for_stack(building, stack)
    if shaft is not None and ShaftService.VENT in shaft.services:
        return shaft
    vent_shafts = [
        item for item in building.shafts if ShaftService.VENT in item.services
    ]
    if not vent_shafts:
        return None
    return min(
        vent_shafts,
        key=lambda item: distance(item.position, stack.position),
    )


def _port_point(shaft: Shaft, x_factor: float, y_factor: float) -> Point:
    return Point(
        x=shaft.position.x + shaft.width_mm / 2 * x_factor,
        y=shaft.position.y + shaft.depth_mm / 2 * y_factor,
    )


def _items(design: Design) -> list[PlumbingItem]:
    source = design.water_source or _water_source(design)
    vent = design.vent_stack or _vent_stack(design)
    items: list[PlumbingItem] = [
        PlumbingItem(
            id="PS-01",
            type=PlumbingItemType.MAIN_SHUTOFF,
            position=Point(x=source.position.x - 140, y=source.position.y + 60),
            tag="MS",
            system="WATER",
            size="25 mm",
        ),
        PlumbingItem(
            id="CV-01",
            type=PlumbingItemType.CHECK_VALVE,
            position=Point(x=source.position.x - 60, y=source.position.y - 80),
            tag="CV",
            system="WATER",
            size="25 mm",
        ),
    ]
    for index, stack in enumerate(design.stacks or [design.stack], start=1):
        room_id = next(
            (
                plan.room_id
                for plan in design.room_plans
                if plan.stack_id == stack.id
            ),
            design.room_id,
        )
        items.append(
            PlumbingItem(
                id=f"CO-{index:02d}",
                type=PlumbingItemType.CLEANOUT,
                position=Point(x=stack.position.x, y=stack.position.y - 90),
                tag=f"CO-{index:02d}",
                system="DRAINAGE",
                size=f"{stack.diameter_mm:g} mm",
                room_id=room_id,
            )
        )
    for index, vent_stack in enumerate(
        design.vent_stacks or ([vent] if vent else []), start=1
    ):
        items.append(
            PlumbingItem(
                id=f"VT-{index:02d}",
                type=PlumbingItemType.VENT_TERMINATION,
                position=Point(
                    x=vent_stack.position.x + 120,
                    y=vent_stack.position.y + 80,
                ),
                tag=f"VT-{index:02d}",
                system="VENT",
                size=f"{vent_stack.diameter_mm:g} mm",
            )
        )
    if source.heater:
        items.extend(
            [
                PlumbingItem(
                    id="WH-01",
                    type=PlumbingItemType.WATER_HEATER,
                    position=Point(x=source.position.x + 260, y=source.position.y + 160),
                    tag="WH",
                    system="HOT_WATER",
                    size=f"{source.heater_capacity_l:.0f} L",
                ),
                PlumbingItem(
                    id="ET-01",
                    type=PlumbingItemType.EXPANSION_TANK,
                    position=Point(x=source.position.x + 260, y=source.position.y + 300),
                    tag="ET",
                    system="HOT_WATER",
                    size="8 L",
                ),
            ]
        )
    stop_index = 0
    for fixture in design.fixtures:
        connections = connections_for(fixture)
        for point, system in (
            (connections.cold, "COLD_WATER"),
            (connections.hot, "HOT_WATER"),
        ):
            if point is None:
                continue
            stop_index += 1
            items.append(
                PlumbingItem(
                    id=f"FS-{stop_index:02d}",
                    type=PlumbingItemType.FIXTURE_STOP,
                    position=Point(x=point.x - 55, y=point.y - 55),
                    tag=f"FS-{stop_index:02d}",
                    system=system,
                    size="15 mm",
                    room_id=fixture.room_id,
                )
            )
    if any(fixture.type == FixtureType.FLOOR_DRAIN for fixture in design.fixtures):
        floor_drain = next(
            fixture for fixture in design.fixtures if fixture.type == FixtureType.FLOOR_DRAIN
        )
        items.append(
            PlumbingItem(
                id="TP-01",
                type=PlumbingItemType.TRAP_PRIMER,
                position=Point(x=floor_drain.position.x + 160, y=floor_drain.position.y + 120),
                tag="TP",
                system="DRAINAGE",
                size="15 mm",
                room_id=floor_drain.room_id,
            )
        )
    return items

