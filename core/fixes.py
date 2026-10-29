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
    "PIPE_MIN_SEGMENT",
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
) -> list[Fix]:
    fixes: list[Fix] = []
    seen: set[str] = set()

    layout_issues = [
        result
        for result in results
        if result.rule_id in LAYOUT_RULES and result.severity != Severity.PASS
    ]
    if layout_issues and candidates:
        ranked: list[tuple[int, int, float, LayoutCandidate, dict[str, int]]] = []
        for candidate in candidates:
            if candidate.id == design.layout_id:
                continue
            trial = _with_candidate(design, candidate)
            try:
                route_design(building, trial, profile)
            except RouteError:
                continue
            counts = summarize(validate_design(building, trial, profile))
            ranked.append(
                (counts["ERROR"], counts["WARNING"], -candidate.score, candidate, counts)
            )
        ranked.sort(key=lambda item: (item[0], item[1], item[2]))
        for errors, warnings, _score, candidate, _counts in ranked[:3]:
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
            if fix_id not in seen:
                fixes.append(
                    Fix(
                        id=fix_id,
                        kind="REROUTE_PIPE",
                        description=f"Re-route {pipe_id} with a tighter obstacle margin.",
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
) -> Design:
    updated = design.model_copy(deep=True)
    if fix.kind == "SELECT_CANDIDATE":
        candidate_id = fix.params.get("candidate_id")
        candidate = next(
            (item for item in (candidates or []) if item.id == candidate_id), None
        )
        if candidate is None:
            raise FixError(f"Candidate {candidate_id!r} is not available.")
        updated.fixtures = [fixture.model_copy(deep=True) for fixture in candidate.fixtures]
        updated.layout_id = candidate.id
        updated.rationale = candidate.rationale_hint
        try:
            route_design(building, updated, profile)
        except RouteError as exc:
            raise FixError(f"Candidate {candidate.id} cannot be routed: {exc}") from exc
        return updated

    if fix.kind in ("ROUTE_DRAINAGE", "REROUTE_PIPE"):
        try:
            route_design(building, updated, profile)
        except RouteError as exc:
            raise FixError(f"Re-route failed: {exc}") from exc
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


def _with_candidate(design: Design, candidate: LayoutCandidate) -> Design:
    trial = design.model_copy(deep=True)
    trial.fixtures = [fixture.model_copy(deep=True) for fixture in candidate.fixtures]
    trial.layout_id = candidate.id
    return trial


def _pipe(design: Design, pipe_id: str | None):
    for pipe in design.pipes:
        if pipe.id == pipe_id:
            return pipe
    raise FixError(f"Unknown pipe {pipe_id!r}.")
