from __future__ import annotations

from core.geometry import Point, distance
from core.models import Building, Design, FixtureType, Room, RoomPlan, Stack


def stacks_for_building(
    building: Building,
    *,
    manual_stack: Point | None = None,
    shaft_id: str | None = None,
) -> list[Stack]:
    if manual_stack is not None:
        return [Stack(id="S1", position=manual_stack)]
    shafts = list(building.shafts)
    if shaft_id is not None:
        shafts = [shaft for shaft in shafts if shaft.id == shaft_id]
    return [
        Stack(id=f"S{index}", position=shaft.position)
        for index, shaft in enumerate(shafts, start=1)
    ]


def nearest_stack(room: Room, stacks: list[Stack]) -> Stack | None:
    if not stacks:
        return None
    center = room.bbox.center
    return min(stacks, key=lambda stack: distance(center, stack.position))


def normalize_design(design: Design) -> Design:
    primary_room = design.room_id
    if not design.room_plans and primary_room:
        design.room_plans = [
            RoomPlan(
                room_id=primary_room,
                fixture_types=_fixture_types(design),
                layout_id=design.layout_id,
                stack_id=design.stack.id,
            )
        ]

    if not design.stacks:
        design.stacks = [design.stack]

    if design.vent_stack is not None:
        if design.vent_stack.stack_id is None:
            design.vent_stack.stack_id = design.stack.id
        if not design.vent_stacks:
            design.vent_stacks = [design.vent_stack]

    stack_ids = {stack.id for stack in design.stacks}
    for plan in design.room_plans:
        if plan.stack_id not in stack_ids:
            plan.stack_id = design.stack.id

    for fixture in design.fixtures:
        if fixture.room_id is None:
            fixture.room_id = primary_room
    for pipe in [*design.pipes, *design.vent_pipes]:
        if pipe.room_id is None:
            pipe.room_id = primary_room
    for pipe in design.supply_pipes:
        if pipe.room_id is None:
            pipe.room_id = primary_room
    for item in design.plumbing_items:
        if item.room_id is None:
            item.room_id = primary_room

    return design


def room_design_view(design: Design, room_id: str) -> Design:
    plan = design.room_plan(room_id)
    view = design.model_copy(deep=True)
    view.room_id = room_id
    view.room_plans = [plan.model_copy(deep=True)]
    view.fixtures = [
        fixture.model_copy(deep=True)
        for fixture in design.fixtures_for_room(room_id)
    ]
    view.pipes = [
        pipe.model_copy(deep=True) for pipe in design.pipes_for_room(room_id)
    ]
    view.vent_pipes = [
        pipe.model_copy(deep=True)
        for pipe in design.vent_pipes
        if pipe.room_id == room_id
    ]
    view.supply_pipes = [
        pipe.model_copy(deep=True)
        for pipe in design.supply_pipes
        if pipe.room_id == room_id
    ]
    view.plumbing_items = [
        item.model_copy(deep=True)
        for item in design.plumbing_items
        if item.room_id == room_id
    ]
    view.stack = design.stack_for_room(room_id)
    view.stacks = [view.stack]
    view.vent_stack = design.vent_stack_for_room(room_id)
    view.vent_stacks = [view.vent_stack] if view.vent_stack else []
    return view


def _fixture_types(design: Design) -> list[FixtureType]:
    return list(dict.fromkeys(fixture.type for fixture in design.fixtures))
