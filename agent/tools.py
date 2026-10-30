from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from core.dxf_export import export_design
from core.fixes import FixError, apply_fix, recommend_fixes
from core.layout import generate_layouts
from core.models import (
    Building,
    Design,
    Fix,
    FixtureType,
    LayoutCandidate,
    Severity,
    Stack,
    ValidationResult,
)
from core.router import RouteError, route_design
from core.rules.engine import RuleProfile, load_profile, summarize, validate_design


class ToolError(ValueError):
    """Invalid tool input or a deterministic tool failure."""


@dataclass
class AgentSession:
    building: Building
    source_path: Path
    out_dir: Path
    room_id: str | None = None
    fixture_types: list[FixtureType] = field(
        default_factory=lambda: [FixtureType.WC, FixtureType.BASIN, FixtureType.SHOWER]
    )
    stack: Stack | None = None
    profile_id: str = "india_nbc_2016"
    candidates: list[LayoutCandidate] = field(default_factory=list)
    design: Design | None = None
    validation: list[ValidationResult] = field(default_factory=list)
    fixes: list[Fix] = field(default_factory=list)
    approved: bool = False
    exported_path: str | None = None
    applied_fixes: list[str] = field(default_factory=list)
    provider_name: str = ""
    model_name: str = ""
    final_answer: str = ""
    design_id: str = ""
    project_id: str = ""
    decisions: list[dict] = field(default_factory=list)
    plan: list[dict] = field(default_factory=list)
    stale: bool = False

    def profile(self) -> RuleProfile:
        return load_profile(self.profile_id)

    def add_decision(self, decision_type: str, **payload) -> None:
        self.decisions.append({"kind": decision_type, "at": time.time(), **payload})

    def ensure_plan(self, reset: bool = False) -> None:
        if self.plan and not reset:
            return
        self.plan = [
            {"id": "inspect", "label": "Inspect drawing", "status": "pending"},
            {"id": "layouts", "label": "Generate layouts", "status": "pending"},
            {"id": "select", "label": "Compare & select", "status": "pending"},
            {"id": "route", "label": "Route drainage", "status": "pending"},
            {"id": "validate", "label": "Validate", "status": "pending"},
            {"id": "fix", "label": "Fix (if needed)", "status": "pending"},
            {"id": "explain", "label": "Explain decisions", "status": "pending"},
        ]

    def update_plan(self, step_id: str, status: str) -> None:
        for step in self.plan:
            if step.get("id") == step_id:
                step["status"] = status
                return

    def require_design(self) -> Design:
        if self.design is None:
            raise ToolError("No layout selected. Call list_layout_options then select_layout.")
        return self.design

    def require_stack(self) -> Stack:
        if self.stack is not None:
            return self.stack
        if self.building.shafts:
            self.stack = Stack(id="S1", position=self.building.shafts[0].position)
            return self.stack
        raise ToolError(
            "No stack selected and the drawing has no shaft. Ask the user to set a stack point."
        )


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Callable[[dict, AgentSession], dict]
    mutating: bool = False

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def run(self, arguments: dict, session: AgentSession) -> dict:
        if not isinstance(arguments, dict):
            raise ToolError(f"{self.name}: arguments must be a JSON object.")
        return self.handler(arguments, session)


def _schema(properties: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def _inspect_plan(arguments: dict, session: AgentSession) -> dict:
    building = session.building
    rooms = [
        {
            "id": room.id,
            "name": room.name,
            "area_m2": round(room.area_m2, 3),
            "width_mm": round(room.bbox.width, 1),
            "height_mm": round(room.bbox.height, 1),
            "closed": room.is_closed,
            "wet_area": room.is_wet_area,
        }
        for room in building.rooms
    ]
    return {
        "building_id": building.id,
        "units": building.units,
        "source_scale": building.source_scale,
        "warnings": building.warnings,
        "rooms": rooms,
        "doors": [
            {"id": door.id, "x": door.position.x, "y": door.position.y, "width_mm": door.width_mm}
            for door in building.doors
        ],
        "shafts": [
            {
                "id": shaft.id,
                "x": shaft.position.x,
                "y": shaft.position.y,
                "width_mm": shaft.width_mm,
                "depth_mm": shaft.depth_mm,
            }
            for shaft in building.shafts
        ],
        "selection": {
            "room_id": session.room_id,
            "fixtures": [fixture.value for fixture in session.fixture_types],
            "stack": (
                {"id": session.stack.id, "x": session.stack.position.x, "y": session.stack.position.y}
                if session.stack
                else None
            ),
            "profile_id": session.profile_id,
        },
    }


def _list_layout_options(arguments: dict, session: AgentSession) -> dict:
    room_id = arguments.get("room_id") or session.room_id
    if not room_id:
        raise ToolError("room_id is required (no room selected in this session).")
    try:
        session.building.room(room_id)
    except KeyError:
        raise ToolError(f"Unknown room {room_id!r}.") from None
    raw_fixtures = arguments.get("fixtures") or [fixture.value for fixture in session.fixture_types]
    try:
        fixture_types = [FixtureType(str(item)) for item in raw_fixtures]
    except ValueError as exc:
        raise ToolError(f"Unknown fixture type in {raw_fixtures!r}.") from exc
    stack = session.require_stack()
    candidates = generate_layouts(
        session.building, room_id, fixture_types, stack.position
    )
    if not candidates:
        raise ToolError(
            "No layout fits this room with the selected fixtures. "
            "Try fewer fixtures, a larger room, or manual placement."
        )
    session.room_id = room_id
    session.fixture_types = fixture_types
    session.candidates = candidates
    return {
        "profile_id": session.profile_id,
        "count": len(candidates),
        "candidates": [
            {
                "id": candidate.id,
                "pattern": candidate.pattern,
                "score": round(candidate.score, 1),
                "violations": candidate.violations,
                "rationale_hint": candidate.rationale_hint,
                "fixtures": [
                    {
                        "id": fixture.id,
                        "type": fixture.type.value,
                        "x": round(fixture.position.x, 1),
                        "y": round(fixture.position.y, 1),
                        "rotation": fixture.rotation_deg,
                    }
                    for fixture in candidate.fixtures
                ],
            }
            for candidate in candidates
        ],
    }


def _select_layout(arguments: dict, session: AgentSession) -> dict:
    candidate_id = arguments.get("candidate_id")
    if not candidate_id:
        raise ToolError("candidate_id is required.")
    candidate = next(
        (item for item in session.candidates if item.id == candidate_id), None
    )
    if candidate is None:
        raise ToolError(
            f"Unknown candidate {candidate_id!r}. Call list_layout_options first."
        )
    stack = session.require_stack()
    rationale = str(arguments.get("rationale") or "").strip()
    if not rationale:
        raise ToolError("rationale is required: explain why this layout was selected.")
    session.design = Design(
        id=session.design_id or "DESIGN-01",
        room_id=session.room_id or "",
        profile_id=session.profile_id,
        stack=stack,
        fixtures=[fixture.model_copy(deep=True) for fixture in candidate.fixtures],
        layout_id=candidate.id,
        rationale=rationale,
        assumptions=[
            "Drainage-only design.",
            "Each fixture has an individual branch and trap.",
            "Vent piping is not modeled; long branches are warnings.",
        ],
    )
    session.validation = []
    session.fixes = []
    session.applied_fixes = []
    selected_score = candidate.score
    rejected = [
        {
            "id": other.id,
            "pattern": other.pattern,
            "score": round(other.score, 1),
            "violations": other.violations,
            "reason": _rejection_reason(other, candidate),
        }
        for other in session.candidates
        if other.id != candidate.id
    ]
    session.add_decision(
        "layout_selected",
        candidate_id=candidate.id,
        pattern=candidate.pattern,
        score=round(selected_score, 1),
        rationale=rationale,
        rejected=rejected,
    )
    return {
        "design_id": session.design.id,
        "layout_id": candidate.id,
        "pattern": candidate.pattern,
        "fixtures": [
            {"id": fixture.id, "type": fixture.type.value}
            for fixture in session.design.fixtures
        ],
        "layout_violations": candidate.violations,
        "rationale": rationale,
        "rejected": rejected,
    }


def _route_drainage(arguments: dict, session: AgentSession) -> dict:
    design = session.require_design()
    try:
        pipes = route_design(session.building, design, session.profile())
    except RouteError as exc:
        session.add_decision(
            "route_failed",
            layout_id=design.layout_id,
            message=str(exc),
        )
        raise ToolError(
            f"{exc} Try list_layout_options and select another candidate."
        ) from exc
    return {
        "design_id": design.id,
        "count": len(pipes),
        "pipes": [
            {
                "id": pipe.id,
                "from_node": pipe.from_node,
                "to_node": pipe.to_node,
                "system": pipe.system.value,
                "diameter_mm": pipe.diameter_mm,
                "slope": pipe.slope,
                "length_mm": round(_length(pipe.points), 1),
                "segments": len(pipe.points) - 1,
            }
            for pipe in pipes
        ],
    }


def _validate_design(arguments: dict, session: AgentSession) -> dict:
    design = session.require_design()
    requested_profile = arguments.get("profile_id")
    if requested_profile and requested_profile != session.profile_id:
        try:
            load_profile(str(requested_profile))
        except KeyError as exc:
            raise ToolError(str(exc)) from exc
        previous_profile = session.profile_id
        session.profile_id = str(requested_profile)
        design.profile_id = session.profile_id
        session.add_decision(
            "profile_changed",
            previous_profile=previous_profile,
            profile_id=session.profile_id,
            reason="Requested validation against another standard.",
        )
    profile = session.profile()
    results = validate_design(session.building, design, profile)
    fixes = recommend_fixes(
        session.building, design, results, profile, session.candidates
    )
    session.validation = results
    session.fixes = fixes
    session.stale = False
    counts = summarize(results)
    session.add_decision(
        "validation",
        profile_id=profile.id,
        counts=counts,
    )
    issues = [
        _result_payload(result)
        for result in results
        if result.severity != Severity.PASS
    ]
    if counts["ERROR"] and fixes:
        next_step = f"Apply a fix, starting with {fixes[0].id}, then validate again."
    elif counts["ERROR"]:
        next_step = "No automatic fix is available. Explain the blocker and ask the engineer."
    elif fixes:
        next_step = "Optional improvement is available. Apply a fix or explain why the warnings are acceptable."
    else:
        next_step = "Explain the design and stop; export requires engineer approval."
    return {
        "design_id": design.id,
        "profile_id": profile.id,
        "counts": counts,
        "issues": issues,
        "fixes": [
            {
                "id": fix.id,
                "kind": fix.kind,
                "description": fix.description,
            }
            for fix in fixes
        ],
        "next_step": next_step,
        "disclaimer": profile.disclaimer,
    }


def _apply_fix(arguments: dict, session: AgentSession) -> dict:
    design = session.require_design()
    fix_id = arguments.get("fix_id")
    if not fix_id:
        raise ToolError("fix_id is required.")
    fix = next((item for item in session.fixes if item.id == fix_id), None)
    if fix is None:
        raise ToolError(
            f"Unknown fix {fix_id!r}. Call validate_design to refresh the fix list."
        )
    try:
        updated = apply_fix(
            session.building, design, fix, session.profile(), session.candidates
        )
    except FixError as exc:
        raise ToolError(str(exc)) from exc
    before = summarize(session.validation) if session.validation else {
        "PASS": 0,
        "WARNING": 0,
        "ERROR": 0,
    }
    session.design = updated
    session.applied_fixes.append(fix.id)
    results = validate_design(session.building, updated, session.profile())
    fixes = recommend_fixes(
        session.building, updated, results, session.profile(), session.candidates
    )
    session.validation = results
    session.fixes = fixes
    counts = summarize(results)
    session.add_decision(
        "fix_applied",
        fix_id=fix.id,
        kind=fix.kind,
        description=fix.description,
        before=before,
        after=counts,
    )
    return {
        "applied": fix.id,
        "description": fix.description,
        "counts": counts,
        "issues": [
            _result_payload(result)
            for result in results
            if result.severity != Severity.PASS
        ],
        "fixes": [
            {"id": item.id, "kind": item.kind, "description": item.description}
            for item in fixes
        ],
    }


def _get_design_state(arguments: dict, session: AgentSession) -> dict:
    selected_id = session.design.layout_id if session.design else None
    counts = summarize(session.validation) if session.validation else {
        "PASS": 0,
        "WARNING": 0,
        "ERROR": 0,
    }
    design = None
    if session.design is not None:
        design = {
            "layout_id": session.design.layout_id,
            "rationale": session.design.rationale,
            "fixtures": [
                {
                    "id": fixture.id,
                    "type": fixture.type.value,
                    "x": round(fixture.position.x, 1),
                    "y": round(fixture.position.y, 1),
                }
                for fixture in session.design.fixtures
            ],
            "pipes": [
                {
                    "id": pipe.id,
                    "from_node": pipe.from_node,
                    "to_node": pipe.to_node,
                    "system": pipe.system.value,
                    "diameter_mm": pipe.diameter_mm,
                    "slope": pipe.slope,
                    "length_mm": round(_length(pipe.points), 1),
                }
                for pipe in session.design.pipes
            ],
        }
    return {
        "room_id": session.room_id,
        "profile_id": session.profile_id,
        "profile_name": session.profile().name,
        "fixtures": [fixture.value for fixture in session.fixture_types],
        "stack": (
            {
                "id": session.stack.id,
                "x": session.stack.position.x,
                "y": session.stack.position.y,
            }
            if session.stack
            else None
        ),
        "design": design,
        "candidates": [
            _candidate_compact(candidate, selected_id)
            for candidate in session.candidates
        ],
        "validation": {
            "counts": counts,
            "issues": [
                _result_payload(result)
                for result in session.validation
                if result.severity != Severity.PASS
            ],
        },
        "fixes": [
            {"id": fix.id, "kind": fix.kind, "description": fix.description}
            for fix in session.fixes
        ],
        "decisions": session.decisions,
        "plan": session.plan,
        "stale": session.stale,
        "disclaimer": session.profile().disclaimer,
    }


def _compare_layouts(arguments: dict, session: AgentSession) -> dict:
    if not session.candidates:
        raise ToolError("No layouts generated yet. Call list_layout_options first.")
    selected = (
        next(
            (
                candidate
                for candidate in session.candidates
                if session.design and candidate.id == session.design.layout_id
            ),
            None,
        )
        if session.design
        else None
    )
    rows = []
    for candidate in session.candidates:
        row = _candidate_compact(candidate, selected.id if selected else None)
        if selected is not None and candidate.id != selected.id:
            row["reason"] = _rejection_reason(candidate, selected)
        elif selected is not None:
            row["reason"] = "Selected: " + (session.design.rationale or "no rationale")
        else:
            row["reason"] = "Not selected yet."
        rows.append(row)
    return {
        "selected_id": selected.id if selected else None,
        "selected_pattern": selected.pattern if selected else None,
        "selected_rationale": session.design.rationale if session.design else None,
        "candidates": rows,
        "note": (
            "Reasons use hard layout violations and the deterministic score. "
            "Candidates are not re-routed or revalidated unless explicitly requested."
        ),
    }


def _set_fixtures(arguments: dict, session: AgentSession) -> dict:
    raw = arguments.get("fixtures")
    if not isinstance(raw, list) or not raw:
        raise ToolError("fixtures must be a non-empty array of fixture types.")
    try:
        fixture_types = [FixtureType(str(item)) for item in raw]
    except ValueError as exc:
        raise ToolError(f"Unknown fixture type in {raw!r}.") from exc
    fixture_types = list(dict.fromkeys(fixture_types))
    previous = [fixture.value for fixture in session.fixture_types]
    session.fixture_types = fixture_types
    session.candidates = []
    session.design = None
    session.validation = []
    session.fixes = []
    session.applied_fixes = []
    session.stale = True
    session.ensure_plan(reset=True)
    session.add_decision(
        "fixtures_changed",
        previous=previous,
        fixtures=[fixture.value for fixture in fixture_types],
    )
    return {
        "fixtures": [fixture.value for fixture in fixture_types],
        "note": "Call list_layout_options to regenerate the layout candidates.",
    }


def _candidate_compact(
    candidate: LayoutCandidate, selected_id: str | None
) -> dict:
    return {
        "id": candidate.id,
        "pattern": candidate.pattern,
        "score": round(candidate.score, 1),
        "violations": candidate.violations,
        "rationale_hint": candidate.rationale_hint,
        "selected": candidate.id == selected_id,
        "fixtures": [
            {
                "id": fixture.id,
                "type": fixture.type.value,
                "x": round(fixture.position.x, 1),
                "y": round(fixture.position.y, 1),
            }
            for fixture in candidate.fixtures
        ],
    }


def _explain_design(arguments: dict, session: AgentSession) -> dict:
    design = session.require_design()
    profile = session.profile()
    counts = summarize(session.validation) if session.validation else summarize(
        validate_design(session.building, design, profile)
    )
    room = session.building.room(design.room_id)
    parts = [
        f"Room {room.id} ({room.name or 'unnamed'}, {room.area_m2:.2f} m2).",
        f"Profile {profile.name}.",
        f"Layout {design.layout_id or 'manual'} "
        f"({(design.rationale or 'no rationale').rstrip('.')}).",
        "Fixtures: "
        + ", ".join(
            f"{fixture.id} at ({fixture.position.x:.0f}, {fixture.position.y:.0f})"
            for fixture in design.fixtures
        )
        + ".",
        "Drainage: "
        + "; ".join(
            f"{pipe.id} {pipe.from_node}->{pipe.to_node} "
            f"{pipe.diameter_mm:g}mm at slope {pipe.slope}"
            for pipe in design.pipes
        )
        + ".",
        f"Validation: {counts['PASS']} PASS, {counts['WARNING']} WARNING, "
        f"{counts['ERROR']} ERROR.",
        "Assumptions: " + " ".join(design.assumptions),
        profile.disclaimer,
    ]
    return {
        "design_id": design.id,
        "explanation": " ".join(parts),
        "counts": counts,
        "disclaimer": profile.disclaimer,
    }


def _export_dxf(arguments: dict, session: AgentSession) -> dict:
    design = session.require_design()
    if not session.approved:
        raise ToolError(
            "Export requires explicit engineer approval. Review the design first."
        )
    if not design.pipes:
        raise ToolError("No pipes are routed; export is blocked.")
    target = session.out_dir / f"{design.id}.dxf"
    path = export_design(
        session.building, design, session.source_path, target
    )
    session.exported_path = path
    return {
        "path": path,
        "layers": ["P-ROOM", "P-SOIL", "P-WASTE", "P-FIXTURE", "P-STACK", "P-TEXT"],
        "engineer_approval_required": True,
    }


def _result_payload(result: ValidationResult) -> dict:
    return {
        "rule_id": result.rule_id,
        "severity": result.severity.value,
        "message": result.message,
        "source": result.source,
        "measured": result.measured,
        "required": result.required,
        "affected": result.affected,
        "fix_ids": result.fix_ids,
    }


def _rejection_reason(candidate: LayoutCandidate, selected: LayoutCandidate) -> str:
    if candidate.violations:
        return "Hard violations: " + "; ".join(candidate.violations)
    if candidate.id != selected.id:
        return (
            f"Lower deterministic score ({candidate.score:.0f} vs "
            f"{selected.score:.0f}) with no hard violation."
        )
    return "Not selected."


def _length(points) -> float:
    total = 0.0
    for index in range(len(points) - 1):
        dx = points[index + 1].x - points[index].x
        dy = points[index + 1].y - points[index].y
        total += (dx * dx + dy * dy) ** 0.5
    return total


def _register(tool: Tool) -> Tool:
    TOOLS[tool.name] = tool
    return tool


TOOLS: dict[str, Tool] = {}

_register(
    Tool(
        "inspect_plan",
        "Inspect the loaded DXF plan: rooms, doors, shafts, units, warnings, and "
        "the current selection.",
        _schema({}),
        _inspect_plan,
    )
)
_register(
    Tool(
        "list_layout_options",
        "Generate deterministic bathroom layout candidates. Returns ranked "
        "candidates with pattern, score, violations, and fixture positions.",
        _schema(
            {
                "room_id": {"type": "string"},
                "fixtures": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [item.value for item in FixtureType],
                    },
                },
            }
        ),
        _list_layout_options,
    )
)
_register(
    Tool(
        "select_layout",
        "Choose one generated layout and record the engineering rationale.",
        _schema(
            {
                "candidate_id": {"type": "string"},
                "rationale": {"type": "string"},
            },
            ["candidate_id", "rationale"],
        ),
        _select_layout,
    )
)
_register(
    Tool(
        "route_drainage",
        "Route every fixture to the stack with orthogonal, obstacle-aware paths "
        "using the selected profile's pipe sizes.",
        _schema({}),
        _route_drainage,
    )
)
_register(
    Tool(
        "validate_design",
        "Validate the design against the selected cited rule pack. Returns "
        "counts, non-pass results with sources, and deterministic fixes.",
        _schema({"profile_id": {"type": "string"}}),
        _validate_design,
    )
)
_register(
    Tool(
        "apply_fix",
        "Apply a deterministic fix from validate_design, then revalidate.",
        _schema({"fix_id": {"type": "string"}}, ["fix_id"]),
        _apply_fix,
    )
)
_register(
    Tool(
        "explain_design",
        "Produce a deterministic engineering summary with counts, assumptions, "
        "and the rule-pack disclaimer.",
        _schema({}),
        _explain_design,
    )
)
_register(
    Tool(
        "get_design_state",
        "Return the current design state: room, standard, fixtures, pipes, "
        "candidates, validation counts, fixes, decisions, and plan. Use this "
        "for follow-up questions.",
        _schema({}),
        _get_design_state,
    )
)
_register(
    Tool(
        "compare_layouts",
        "Compare all generated layouts against the selected one, including "
        "deterministic rejection reasons.",
        _schema({}),
        _compare_layouts,
    )
)
_register(
    Tool(
        "set_fixtures",
        "Change the fixture set and clear the current design so the agent can "
        "generate new layouts. Does not place fixtures manually.",
        _schema(
            {
                "fixtures": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [item.value for item in FixtureType],
                    },
                }
            },
            ["fixtures"],
        ),
        _set_fixtures,
    )
)
_register(
    Tool(
        "export_dxf",
        "Export the approved design over the source DXF. Requires explicit "
        "engineer approval.",
        _schema({}),
        _export_dxf,
        mutating=True,
    )
)


def tool_schemas() -> list[dict]:
    return [tool.schema() for tool in TOOLS.values()]
