from __future__ import annotations

from core.models import Building, Design, Fix, LayoutCandidate, Severity
from core.router import RouteError, route_design
from core.rules.engine import RuleProfile, summarize, validate_design

LAYOUT_RULES = {
    "FIXTURE_INSIDE_ROOM",
    "FIXTURE_SIDE_CLEARANCE",
    "FIXTURE_FRONT_CLEARANCE",
    "FIXTURE_SPACING",
    "FIXTURE_OVERLAP",
    "DOOR_SWING",
    "STACK_OBSTRUCTION",
    "SHOWER_SIZE",
    "NO_FIXTURES",
}
ROUTE_RULES = {
    "PIPE_CONTAINMENT",
    "PIPE_FIXTURE_CROSSING",
    "PIPE_DOOR_CROSSING",
}


class FixError(ValueError):
    """A deterministic fix could not be applied."""


def recommend_fixes(
    building: Building,
    design: Design,
    results: list,
    profile: RuleProfile,
    candidates: list[LayoutCandidate] | None = None,
    candidates_by_room: dict[str, list[LayoutCandidate]] | None = None,
) -> list[Fix]:
    fixes: list[Fix] = []
    seen: set[str] = set()
    current = summarize(results)

    layout_issues = [
        result
        for result in results
        if result.rule_id in LAYOUT_RULES and result.severity != Severity.PASS
    ]
    if layout_issues and candidates_by_room:
        rooms = {
            result.affected.get("room_id")
            for result in layout_issues
            if result.affected.get("room_id")
        }
        for room_id in rooms:
            room_candidates = candidates_by_room.get(room_id) or []
            current_layout = (
                design.room_plan(room_id).layout_id
                if design.room_plans
                else design.layout_id
            )
            ranked = _rank_candidates(
                building,
                design,
                profile,
                current,
                [
                    candidate
                    for candidate in room_candidates
                    if candidate.id != current_layout
                ],
                room_id=room_id,
            )
            for errors, warnings, candidate in ranked[:3]:
                fix_id = f"switch:{room_id}:{candidate.id}"
                fixes.append(
                    Fix(
                        id=fix_id,
                        kind="SELECT_CANDIDATE",
                        description=(
                            f"Switch {room_id} to {candidate.pattern} layout "
                            f"{candidate.id}: {errors} errors, {warnings} warnings "
                            "after routing."
                        ),
                        affected={
                            "room_id": room_id,
                            "layout_id": current_layout or "",
                        },
                        params={
                            "room_id": room_id,
                            "candidate_id": candidate.id,
                        },
                    )
                )
                seen.add(fix_id)
    elif layout_issues and candidates:
        ranked = _rank_candidates(
            building,
            design,
            profile,
            current,
            [
                candidate
                for candidate in candidates
                if candidate.id != design.layout_id
            ],
        )
        for errors, warnings, candidate in ranked[:3]:
            fix_id = f"switch:{candidate.id}"
            fixes.append(
                Fix(
                    id=fix_id,
                    kind="SELECT_CANDIDATE",
                    description=(
                        f"Switch to {candidate.pattern} layout {candidate.id}: "
                        f"{errors} errors, {warnings} warnings after routing."
                    ),
                    affected={"layout_id": design.layout_id or ""},
                    params={"candidate_id": candidate.id},
                )
            )
            seen.add(fix_id)

    for result in results:
        if result.severity == Severity.PASS:
            continue
        pipe_id = result.affected.get("pipe_id")
        if result.rule_id == "PIPE_ROUTING":
            if "route" not in seen:
                fixes.append(
                    Fix(
                        id="route",
                        kind="ROUTE_DRAINAGE",
                        description="Route every fixture to the stack.",
                    )
                )
                seen.add("route")
            continue
        if pipe_id and result.rule_id in ROUTE_RULES:
            fix_id = f"reroute:{pipe_id}"
            if fix_id in seen:
                continue
            trial = design.model_copy(deep=True)
            try:
                route_design(building, trial, profile)
            except RouteError:
                continue
            counts = summarize(validate_design(building, trial, profile))
            if counts["ERROR"] >= current["ERROR"] and counts["WARNING"] >= current["WARNING"]:
                continue
            fixes.append(
                Fix(
                    id=fix_id,
                    kind="REROUTE_PIPE",
                    description=f"Re-route {pipe_id} with a different obstacle strategy.",
                    affected={"pipe_id": pipe_id},
                    params={"pipe_id": pipe_id},
                )
            )
            seen.add(fix_id)
        if pipe_id and result.rule_id == "PIPE_DIAMETER":
            fix_id = f"size:{pipe_id}"
            if fix_id not in seen:
                fixes.append(
                    Fix(
                        id=fix_id,
                        kind="CHANGE_PIPE_SIZE",
                        description=f"Set {pipe_id} to the profile-required diameter.",
                        affected={"pipe_id": pipe_id},
                        params={"pipe_id": pipe_id},
                    )
                )
                seen.add(fix_id)
        if pipe_id and result.rule_id == "PIPE_SLOPE":
            fix_id = f"slope:{pipe_id}"
            if fix_id not in seen:
                fixes.append(
                    Fix(
                        id=fix_id,
                        kind="ADJUST_SLOPE",
                        description=f"Move {pipe_id} slope into the profile range.",
                        affected={"pipe_id": pipe_id},
                        params={"pipe_id": pipe_id},
                    )
                )
                seen.add(fix_id)
    return fixes[:6]


def apply_fix(
    building: Building,
    design: Design,
    fix: Fix,
    profile: RuleProfile,
    candidates: list[LayoutCandidate] | None = None,
    candidates_by_room: dict[str, list[LayoutCandidate]] | None = None,
) -> Design:
    updated = design.model_copy(deep=True)
    if fix.kind == "SELECT_CANDIDATE":
        candidate_id = fix.params.get("candidate_id")
        room_id = fix.params.get("room_id")
        pool = (
            (candidates_by_room or {}).get(str(room_id), [])
            if room_id
            else (candidates or [])
        )
        candidate = next(
            (item for item in pool if item.id == candidate_id), None
        )
        if candidate is None:
            raise FixError(f"Candidate {candidate_id!r} is not available.")
        if room_id:
            updated = _with_candidate_in_room(updated, str(room_id), candidate)
            updated.room_plan(str(room_id)).rationale = fix.description
        else:
            updated.fixtures = [
                fixture.model_copy(deep=True) for fixture in candidate.fixtures
            ]
            updated.layout_id = candidate.id
            updated.rationale = fix.description
        try:
            route_design(building, updated, profile)
        except RouteError as exc:
            raise FixError(f"Candidate {candidate.id} cannot be routed: {exc}") from exc
        return updated

    if fix.kind in ("ROUTE_DRAINAGE", "REROUTE_PIPE"):
        before = summarize(validate_design(building, updated, profile))
        try:
            route_design(building, updated, profile)
        except RouteError as exc:
            raise FixError(f"Re-route failed: {exc}") from exc
        after = summarize(validate_design(building, updated, profile))
        if (
            fix.kind == "REROUTE_PIPE"
            and after["ERROR"] >= before["ERROR"]
            and after["WARNING"] >= before["WARNING"]
        ):
            raise FixError(
                "Re-route did not improve the drawing. This room and fixture set "
                "need a layout change, fewer fixtures, or a larger room."
            )
        return updated

    if fix.kind == "ADJUST_SLOPE":
        pipe = _pipe(updated, fix.params.get("pipe_id"))
        rule = profile.slope_for(pipe.system)
        current = pipe.slope if pipe.slope is not None else rule.default
        pipe.slope = min(max(current, rule.min), rule.max)
        return updated

    if fix.kind == "CHANGE_PIPE_SIZE":
        pipe = _pipe(updated, fix.params.get("pipe_id"))
        fixture = next(
            (item for item in updated.fixtures if item.id == pipe.from_node), None
        )
        if fixture is None:
            raise FixError(f"Pipe {pipe.id} has no source fixture.")
        pipe.diameter_mm = profile.pipe_for(fixture.type).diameter_mm
        return updated

    raise FixError(f"Unsupported fix kind {fix.kind!r}.")


def _rank_candidates(
    building: Building,
    design: Design,
    profile: RuleProfile,
    current: dict[str, int],
    candidates: list[LayoutCandidate],
    *,
    room_id: str | None = None,
) -> list[tuple[int, int, LayoutCandidate]]:
    ranked: list[tuple[int, int, float, LayoutCandidate]] = []
    for candidate in candidates:
        trial = (
            _with_candidate_in_room(design, room_id, candidate)
            if room_id
            else _with_candidate(design, candidate)
        )
        try:
            route_design(building, trial, profile)
        except RouteError:
            continue
        counts = summarize(validate_design(building, trial, profile))
        if counts["ERROR"] > current["ERROR"]:
            continue
        if (
            counts["ERROR"] == current["ERROR"]
            and counts["WARNING"] >= current["WARNING"]
        ):
            continue
        ranked.append(
            (
                counts["ERROR"],
                counts["WARNING"],
                -candidate.score,
                candidate,
            )
        )
    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    return [(errors, warnings, candidate) for errors, warnings, _, candidate in ranked]


def _with_candidate(design: Design, candidate: LayoutCandidate) -> Design:
    trial = design.model_copy(deep=True)
    trial.fixtures = [fixture.model_copy(deep=True) for fixture in candidate.fixtures]
    trial.layout_id = candidate.id
    return trial


def _with_candidate_in_room(
    design: Design, room_id: str, candidate: LayoutCandidate
) -> Design:
    trial = design.model_copy(deep=True)
    plan = trial.room_plan(room_id)
    plan.layout_id = candidate.id
    trial.fixtures = [
        fixture
        for fixture in trial.fixtures
        if fixture.room_id != room_id
    ] + [
        fixture.model_copy(
            update={
                "id": (
                    f"{room_id}-{fixture.id}"
                    if len(trial.room_plans) > 1
                    else fixture.id
                ),
                "room_id": room_id,
            },
            deep=True,
        )
        for fixture in candidate.fixtures
    ]
    if design.room_id == room_id:
        trial.layout_id = candidate.id
    return trial


def _pipe(design: Design, pipe_id: str | None):
    for pipe in design.pipes:
        if pipe.id == pipe_id:
            return pipe
    raise FixError(f"Unknown pipe {pipe_id!r}.")
