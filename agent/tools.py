from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from core.consolidated import stacks_for_building
from core.fixes import FixError, apply_fix, recommend_fixes
from core.layout import generate_layouts
from core.models import (
    SHEET_PRESETS_MM,
    Building,
    Design,
    DrawingCheck,
    Fix,
    FixtureType,
    LayoutCandidate,
    RoomPlan,
    Severity,
    SheetSpec,
    Stack,
    ValidationResult,
)
from core.plumbing import build_plumbing
from core.router import RouteError, route_design
from core.rules.engine import RuleProfile, load_profile, summarize, validate_design
from core.sheet import prepare_sheet as prepare_sheet_files
from core.sheet import sheet_counts


class ToolError(ValueError):
    """Invalid tool input or a deterministic tool failure."""


@dataclass
class RoomChoice:
    room_id: str
    fixture_types: list[FixtureType] = field(
        default_factory=lambda: [FixtureType.WC, FixtureType.BASIN, FixtureType.SHOWER]
    )
    stack_id: str = "S1"


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
    stacks: dict[str, Stack] = field(default_factory=dict)
    room_choices: list[RoomChoice] = field(default_factory=list)
    profile_id: str = "india_nbc_2016"
    candidates_by_room: dict[str, list[LayoutCandidate]] = field(default_factory=dict)
    selected_candidates: dict[str, LayoutCandidate] = field(default_factory=dict)
    room_rationales: dict[str, str] = field(default_factory=dict)
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
    drawing_review: list[DrawingCheck] = field(default_factory=list)
    sheet_ready: bool = False
    sheet_path: str | None = None
    sheet_svg_path: str | None = None
    sheet_pdf_path: str | None = None
    sheet_pages: int = 0

    def __post_init__(self) -> None:
        if self.stack is not None:
            self.stacks.setdefault(self.stack.id, self.stack)
        if not self.room_choices and self.room_id:
            stack_id = self.stack.id if self.stack else "S1"
            self.room_choices = [
                RoomChoice(self.room_id, list(self.fixture_types), stack_id)
            ]
        if self.room_choices:
            first = self.room_choices[0]
            self.room_id = self.room_id or first.room_id
            if self.room_id == first.room_id:
                self.fixture_types = list(first.fixture_types)
                if self.stack is None:
                    self.stack = self.stacks.get(first.stack_id)

    @property
    def candidates(self) -> list[LayoutCandidate]:
        return self.candidates_by_room.get(self.room_id or "", [])

    @candidates.setter
    def candidates(self, candidates: list[LayoutCandidate]) -> None:
        if self.room_id:
            self.candidates_by_room[self.room_id] = list(candidates)

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
            {"id": "services", "label": "Route water & vent", "status": "pending"},
            {"id": "sheet", "label": "Prepare sheet", "status": "pending"},
            {"id": "validate", "label": "Validate", "status": "pending"},
            {"id": "fix", "label": "Fix (if needed)", "status": "pending"},
            {"id": "explain", "label": "Explain decisions", "status": "pending"},
        ]

    def update_plan(self, step_id: str, status: str) -> None:
        for step in self.plan:
            if step.get("id") == step_id:
                step["status"] = status
                return

    def room_choice(self, room_id: str) -> RoomChoice | None:
        return next(
            (choice for choice in self.room_choices if choice.room_id == room_id),
            None,
        )

    def require_design(self) -> Design:
        if self.design is None:
            raise ToolError("No layout selected. Call plan_room_layouts first.")
        return self.design

    def require_stack(self, room_id: str | None = None) -> Stack:
        target = room_id or self.room_id
        choice = self.room_choice(target) if target else None
        if choice is not None:
            stack = self.stacks.get(choice.stack_id)
            if stack is not None:
                return stack
        if self.stack is not None:
            return self.stack
        stacks = stacks_for_building(self.building)
        if stacks:
            self.stack = stacks[0]
            self.stacks[self.stack.id] = self.stack
            return self.stack
        raise ToolError(
            "No stack selected and the drawing has no shaft. Ask the user to set a stack point."
        )

    def sync_design_from_layouts(self) -> None:
        selected = [
            (choice, self.selected_candidates[choice.room_id])
            for choice in self.room_choices
            if choice.room_id in self.selected_candidates
        ]
        if not selected:
            self.design = None
            return
        primary_room = self.room_id or selected[0][0].room_id
        primary = next(
            (item for item in selected if item[0].room_id == primary_room),
            selected[0],
        )
        stacks: dict[str, Stack] = {}
        for choice, _ in selected:
            stack = self.require_stack(choice.room_id)
            stacks[stack.id] = stack
        primary_stack = self.require_stack(primary[0].room_id)
        self.stack = primary_stack
        self.room_id = primary[0].room_id
        self.fixture_types = list(primary[0].fixture_types)
        self.design = Design(
            id=self.design_id or "DESIGN-01",
            room_id=primary[0].room_id,
            profile_id=self.profile_id,
            layout_id=primary[1].id,
            room_plans=[
                RoomPlan(
                    room_id=choice.room_id,
                    fixture_types=list(choice.fixture_types),
                    layout_id=candidate.id,
                    stack_id=self.require_stack(choice.room_id).id,
                    rationale=self.room_rationales.get(choice.room_id),
                )
                for choice, candidate in selected
            ],
            fixtures=[
                fixture.model_copy(
                    update={
                        "id": (
                            f"{choice.room_id}-{fixture.id}"
                            if len(selected) > 1
                            else fixture.id
                        ),
                        "room_id": choice.room_id,
                    },
                    deep=True,
                )
                for choice, candidate in selected
                for fixture in candidate.fixtures
            ],
            stack=primary_stack,
            stacks=list(stacks.values()),
            sheet=SheetSpec(
                title=(
                    "Floor Plumbing Plan"
                    if len(selected) > 1
                    else "Bathroom Plumbing Plan"
                )
            ),
            rationale=" ".join(
                value
                for value in (
                    self.room_rationales.get(choice.room_id)
                    for choice, _ in selected
                )
                if value
            )
            or None,
            assumptions=[
                "Drainage, vent, and domestic hot/cold water routes are modeled.",
                "Plan and riser routes are schematic; coordinate ceiling and wall voids.",
                "Rule packs are POC subsets, not compliance certificates.",
            ],
        )
        self.validation = []
        self.fixes = []
        self.applied_fixes = []
        _reset_sheet(self)


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


def _reset_sheet(session: AgentSession, *, clear_services: bool = False) -> None:
    session.sheet_ready = False
    session.drawing_review = []
    session.sheet_path = None
    session.sheet_svg_path = None
    session.sheet_pdf_path = None
    session.sheet_pages = 0
    if clear_services and session.design is not None:
        session.design.vent_pipes = []
        session.design.supply_pipes = []
        session.design.plumbing_items = []
        session.design.vent_stack = None
        session.design.water_source = None


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
            "fixtures": [
                _fixture_payload(fixture)
                for fixture in building.detected_fixtures
                if fixture.room_id == room.id
            ],
        }
        for room in building.rooms
    ]
    return {
        "building_id": building.id,
        "units": building.units,
        "source_scale": building.source_scale,
        "warnings": building.warnings,
        "rooms": rooms,
        "detected_fixtures": [
            _fixture_payload(fixture) for fixture in building.detected_fixtures
        ],
        "doors": [
            {"id": door.id, "x": door.position.x, "y": door.position.y, "width_mm": door.width_mm}
            for door in building.doors
        ],
        "shafts": [
            {
                "id": shaft.id,
                "name": shaft.name,
                "x": shaft.position.x,
                "y": shaft.position.y,
                "width_mm": shaft.width_mm,
                "depth_mm": shaft.depth_mm,
                "services": [service.value for service in shaft.services],
                "source": shaft.source,
                "confidence": shaft.confidence,
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


def _fixture_payload(fixture) -> dict:
    return {
        "id": fixture.id,
        "type": fixture.type.value,
        "room_id": fixture.room_id,
        "x": round(fixture.position.x, 1),
        "y": round(fixture.position.y, 1),
        "width_mm": round(fixture.width_mm, 1),
        "depth_mm": round(fixture.depth_mm, 1),
        "block_name": fixture.block_name,
        "source": fixture.source,
        "confidence": fixture.confidence,
    }


def _list_layout_options(arguments: dict, session: AgentSession) -> dict:
    room_id = arguments.get("room_id") or session.room_id
    if not room_id:
        raise ToolError("room_id is required (no room selected in this session).")
    try:
        session.building.room(room_id)
    except KeyError:
        raise ToolError(f"Unknown room {room_id!r}.") from None
    choice = session.room_choice(room_id)
    default_fixtures = (
        choice.fixture_types if choice else session.fixture_types
    )
    raw_fixtures = arguments.get("fixtures") or [
        fixture.value for fixture in default_fixtures
    ]
    try:
        fixture_types = [FixtureType(str(item)) for item in raw_fixtures]
    except ValueError as exc:
        raise ToolError(f"Unknown fixture type in {raw_fixtures!r}.") from exc
    stack = session.require_stack(room_id)
    candidates = generate_layouts(
        session.building, room_id, fixture_types, stack.position
    )
    if not candidates:
        raise ToolError(
            "No layout fits this room with the selected fixtures. "
            "Try fewer fixtures, a larger room, or manual placement."
        )
    if choice is None:
        choice = RoomChoice(room_id, list(fixture_types), stack.id)
        session.room_choices.append(choice)
    choice.fixture_types = list(fixture_types)
    session.candidates_by_room[room_id] = candidates
    if room_id == session.room_id:
        session.fixture_types = fixture_types
    return {
        "room_id": room_id,
        "stack_id": stack.id,
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


def _plan_room_layouts(arguments: dict, session: AgentSession) -> dict:
    if not session.room_choices:
        return {
            "rooms": [],
            "failures": [{"room_id": "", "error": "No rooms selected."}],
        }

    results: list[dict] = []
    failures: list[dict] = []
    for choice in session.room_choices:
        try:
            room = session.building.room(choice.room_id)
        except KeyError:
            failures.append(
                {"room_id": choice.room_id, "error": "Unknown room."}
            )
            continue
        try:
            stack = session.require_stack(choice.room_id)
        except ToolError as exc:
            failures.append({"room_id": choice.room_id, "error": str(exc)})
            continue
        fixture_types = list(choice.fixture_types or room.default_fixtures)
        candidates = generate_layouts(
            session.building,
            choice.room_id,
            fixture_types,
            stack.position,
        )
        if not candidates:
            failures.append(
                {
                    "room_id": choice.room_id,
                    "error": (
                        "No layout fits this room with the selected fixtures."
                    ),
                }
            )
            continue
        candidate = next(
            (item for item in candidates if not item.violations),
            candidates[0],
        )
        rationale = (
            f"Selected {candidate.pattern} layout {candidate.id}: "
            f"{candidate.rationale_hint.rstrip('.')}."
        )
        choice.fixture_types = fixture_types
        session.candidates_by_room[choice.room_id] = candidates
        session.selected_candidates[choice.room_id] = candidate
        session.room_rationales[choice.room_id] = rationale
        session.add_decision(
            "layout_selected",
            room_id=choice.room_id,
            candidate_id=candidate.id,
            pattern=candidate.pattern,
            score=round(candidate.score, 1),
            rationale=rationale,
            rejected=[
                {
                    "id": other.id,
                    "pattern": other.pattern,
                    "score": round(other.score, 1),
                    "violations": other.violations,
                    "reason": _rejection_reason(other, candidate),
                }
                for other in candidates
                if other.id != candidate.id
            ],
        )
        results.append(
            {
                "room_id": choice.room_id,
                "stack_id": stack.id,
                "layout_id": candidate.id,
                "pattern": candidate.pattern,
                "fixture_count": len(candidate.fixtures),
            }
        )

    session.sync_design_from_layouts()
    return {
        "design_id": session.design.id if session.design else None,
        "rooms": results,
        "failures": failures,
    }


def _select_layout(arguments: dict, session: AgentSession) -> dict:
    room_id = arguments.get("room_id") or session.room_id
    if not room_id:
        raise ToolError("room_id is required (no room selected in this session).")
    candidate_id = arguments.get("candidate_id")
    if not candidate_id:
        raise ToolError("candidate_id is required.")
    candidates = session.candidates_by_room.get(room_id, [])
    candidate = next((item for item in candidates if item.id == candidate_id), None)
    if candidate is None:
        raise ToolError(
            f"Unknown candidate {candidate_id!r}. Call list_layout_options first."
        )
    rationale = str(arguments.get("rationale") or "").strip()
    if not rationale:
        raise ToolError("rationale is required: explain why this layout was selected.")
    session.selected_candidates[room_id] = candidate
    session.room_rationales[room_id] = rationale
    session.sync_design_from_layouts()
    selected_score = candidate.score
    rejected = [
        {
            "id": other.id,
            "pattern": other.pattern,
            "score": round(other.score, 1),
            "violations": other.violations,
            "reason": _rejection_reason(other, candidate),
        }
        for other in candidates
        if other.id != candidate.id
    ]
    session.add_decision(
        "layout_selected",
        room_id=room_id,
        candidate_id=candidate.id,
        pattern=candidate.pattern,
        score=round(selected_score, 1),
        rationale=rationale,
        rejected=rejected,
    )
    design = session.require_design()
    return {
        "design_id": design.id,
        "room_id": room_id,
        "layout_id": candidate.id,
        "pattern": candidate.pattern,
        "fixtures": [
            {"id": fixture.id, "type": fixture.type.value}
            for fixture in design.fixtures_for_room(room_id)
        ],
        "layout_violations": candidate.violations,
        "rationale": rationale,
        "rejected": rejected,
    }


def _route_drainage(arguments: dict, session: AgentSession) -> dict:
    design = session.require_design()
    design.vent_pipes = []
    design.supply_pipes = []
    design.plumbing_items = []
    design.vent_stack = None
    design.water_source = None
    _reset_sheet(session)
    pipes = route_design(session.building, design, session.profile())
    if not pipes and design.route_failures:
        session.add_decision(
            "route_failed",
            layout_id=design.layout_id,
            message="; ".join(design.route_failures),
        )
        raise ToolError(
            "No fixture could be routed to its stack. Try another layout or stack."
        )
    return {
        "design_id": design.id,
        "count": len(pipes),
        "failures": list(design.route_failures),
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


def _route_services(arguments: dict, session: AgentSession) -> dict:
    design = session.require_design()
    profile = session.profile()
    _reset_sheet(session)
    try:
        build_plumbing(session.building, design, profile)
    except RouteError as exc:
        raise ToolError(
            f"{exc} Check the water source and vent stack positions or try another layout."
        ) from exc
    session.add_decision(
        "services_routed",
        vent_pipes=len(design.vent_pipes),
        supply_pipes=len(design.supply_pipes),
        plumbing_items=len(design.plumbing_items),
    )
    _reset_sheet(session)
    return {
        "vent_stack": design.vent_stack.model_dump(mode="json") if design.vent_stack else None,
        "water_source": design.water_source.model_dump(mode="json")
        if design.water_source
        else None,
        "vent_pipes": [
            {
                "id": pipe.id,
                "system": pipe.system.value,
                "diameter_mm": pipe.diameter_mm,
                "from_node": pipe.from_node,
                "to_node": pipe.to_node,
                "length_mm": round(_length(pipe.points), 1),
            }
            for pipe in design.vent_pipes
        ],
        "supply_pipes": [
            {
                "id": pipe.id,
                "system": pipe.system.value,
                "diameter_mm": pipe.diameter_mm,
                "from_node": pipe.from_node,
                "to_node": pipe.to_node,
                "material": pipe.material,
                "length_mm": round(_length(pipe.points), 1),
            }
            for pipe in design.supply_pipes
        ],
        "plumbing_items": [
            {
                "id": item.id,
                "type": item.type.value,
                "tag": item.tag,
                "size": item.size,
                "system": item.system,
            }
            for item in design.plumbing_items
        ],
        "counts": {
            "vent_pipes": len(design.vent_pipes),
            "supply_pipes": len(design.supply_pipes),
            "items": len(design.plumbing_items),
        },
        "next_step": "Validate the design, then prepare the sheet.",
    }


def _prepare_sheet_tool(arguments: dict, session: AgentSession) -> dict:
    design = session.require_design()
    if (
        not design.vent_pipes
        or not design.supply_pipes
        or not design.plumbing_items
    ):
        build_plumbing(session.building, design, session.profile())
    result = prepare_sheet_files(
        session.building,
        design,
        session.profile(),
        session.source_path,
        session.out_dir,
        project_name=session.source_path.stem,
    )
    design.sheet.scale = result.scale_used
    session.drawing_review = result.review
    session.sheet_ready = True
    session.sheet_path = str(result.dxf_path)
    session.sheet_svg_path = str(result.svg_paths[0]) if result.svg_paths else None
    session.sheet_pdf_path = str(result.pdf_path)
    session.sheet_pages = result.pages
    counts = sheet_counts(result.review)
    session.add_decision(
        "sheet_prepared",
        pages=result.pages,
        scale=result.scale_used,
        counts=counts,
    )
    issues = [
        item.model_dump(mode="json")
        for item in result.review
        if item.severity != Severity.PASS
    ]
    if counts["ERROR"]:
        next_step = "Fix the drawing errors before export."
    elif counts["ERROR"]:
        next_step = "Resolve the drawing errors before export."
    else:
        next_step = "Review the drawing and explain the result; export requires engineer approval."
    return {
        "ready": True,
        "pages": result.pages,
        "scale": result.scale_used,
        "sheet": design.sheet.model_dump(mode="json"),
        "counts": counts,
        "issues": issues,
        "sheet_url": f"/api/designs/{session.design_id}/sheet.svg",
        "pdf_url": f"/api/designs/{session.design_id}/sheet.pdf",
        "next_step": next_step,
    }


def _set_sheet_options(arguments: dict, session: AgentSession) -> dict:
    design = session.require_design()
    spec = design.sheet.model_copy(deep=True)
    preset = str(arguments.get("preset") or spec.preset).upper()
    if preset != "CUSTOM" and preset not in SHEET_PRESETS_MM:
        raise ToolError(
            "Unknown sheet preset. Use one of "
            + ", ".join([*SHEET_PRESETS_MM, "CUSTOM"])
            + "."
        )
    spec.preset = preset
    if preset in SHEET_PRESETS_MM:
        width, height = SHEET_PRESETS_MM[preset]
        spec.width_mm, spec.height_mm = width, height
    if "width_mm" in arguments:
        spec.width_mm = float(arguments["width_mm"])
        spec.preset = "CUSTOM"
    if "height_mm" in arguments:
        spec.height_mm = float(arguments["height_mm"])
        spec.preset = "CUSTOM"
    if spec.preset == "CUSTOM" and (spec.width_mm < 100 or spec.height_mm < 100):
        raise ToolError("Custom sheet width and height must be at least 100 mm.")
    orientation = str(arguments.get("orientation") or spec.orientation).lower()
    if orientation not in ("landscape", "portrait"):
        raise ToolError("orientation must be landscape or portrait.")
    spec.orientation = orientation
    if "scale" in arguments:
        scale = float(arguments["scale"])
        if scale < 5 or scale > 500:
            raise ToolError("scale must be between 1:5 and 1:500.")
        spec.scale = scale
    for key in ("include_riser", "include_schedules"):
        if key in arguments:
            setattr(spec, key, bool(arguments[key]))
    if "notes" in arguments and isinstance(arguments["notes"], list):
        spec.notes = [str(note) for note in arguments["notes"]][:8]
    design.sheet = spec
    _reset_sheet(session)
    session.add_decision("sheet_options", sheet=spec.model_dump(mode="json"))
    return {
        "sheet": spec.model_dump(mode="json"),
        "next_step": "Prepare the sheet to refresh the preview and drawing checks.",
    }


def _review_drawing(arguments: dict, session: AgentSession) -> dict:
    session.require_design()
    if not session.sheet_ready or not session.sheet_path:
        _prepare_sheet_tool({}, session)
    checks = session.drawing_review
    counts = sheet_counts(checks)
    issues = [
        item.model_dump(mode="json")
        for item in checks
        if item.severity != Severity.PASS
    ]
    return {
        "ready": session.sheet_ready,
        "counts": counts,
        "issues": issues,
        "next_step": (
            "Fix the drawing errors before export."
            if counts["ERROR"]
            else "Explain the sheet and stop; export requires engineer approval."
        ),
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
        session.building,
        design,
        results,
        profile,
        session.candidates,
        session.candidates_by_room,
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
    _reset_sheet(session)
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
            session.building,
            design,
            fix,
            session.profile(),
            session.candidates,
            session.candidates_by_room,
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
    try:
        build_plumbing(session.building, updated, session.profile())
    except RouteError:
        pass
    results = validate_design(session.building, updated, session.profile())
    fixes = recommend_fixes(
        session.building,
        updated,
        results,
        session.profile(),
        session.candidates,
        session.candidates_by_room,
    )
    session.validation = results
    session.fixes = fixes
    counts = summarize(results)
    _reset_sheet(session)
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
            "vent_pipes": [
                {
                    "id": pipe.id,
                    "system": "VENT",
                    "diameter_mm": pipe.diameter_mm,
                    "length_mm": round(_length(pipe.points), 1),
                }
                for pipe in session.design.vent_pipes
            ],
            "supply_pipes": [
                {
                    "id": pipe.id,
                    "system": pipe.system.value,
                    "diameter_mm": pipe.diameter_mm,
                    "material": pipe.material,
                    "length_mm": round(_length(pipe.points), 1),
                }
                for pipe in session.design.supply_pipes
            ],
            "plumbing_items": [
                {
                    "id": item.id,
                    "type": item.type.value,
                    "tag": item.tag,
                    "size": item.size,
                }
                for item in session.design.plumbing_items
            ],
            "sheet": session.design.sheet.model_dump(mode="json"),
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
        "sheet_ready": session.sheet_ready,
        "sheet_pages": session.sheet_pages,
        "drawing_review": {
            "counts": sheet_counts(session.drawing_review),
            "issues": [
                item.model_dump(mode="json")
                for item in session.drawing_review
                if item.severity != Severity.PASS
            ],
        },
        "disclaimer": session.profile().disclaimer,
    }


def _compare_layouts(arguments: dict, session: AgentSession) -> dict:
    room_id = arguments.get("room_id") or session.room_id
    candidates = session.candidates_by_room.get(room_id or "", [])
    if not candidates:
        raise ToolError("No layouts generated yet. Call list_layout_options first.")
    selected = session.selected_candidates.get(room_id or "")
    rationale = session.room_rationales.get(room_id or "") or (
        session.design.rationale if session.design else None
    )
    rows = []
    for candidate in candidates:
        row = _candidate_compact(candidate, selected.id if selected else None)
        if selected is not None and candidate.id != selected.id:
            row["reason"] = _rejection_reason(candidate, selected)
        elif selected is not None:
            row["reason"] = "Selected: " + (rationale or "no rationale")
        else:
            row["reason"] = "Not selected yet."
        rows.append(row)
    return {
        "room_id": room_id,
        "selected_id": selected.id if selected else None,
        "selected_pattern": selected.pattern if selected else None,
        "selected_rationale": rationale,
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
    room_id = arguments.get("room_id") or session.room_id
    if not room_id:
        raise ToolError("room_id is required (no room selected in this session).")
    choice = session.room_choice(room_id)
    if choice is None:
        raise ToolError(f"Unknown room choice {room_id!r}.")
    try:
        fixture_types = [FixtureType(str(item)) for item in raw]
    except ValueError as exc:
        raise ToolError(f"Unknown fixture type in {raw!r}.") from exc
    fixture_types = list(dict.fromkeys(fixture_types))
    previous = [fixture.value for fixture in choice.fixture_types]
    choice.fixture_types = fixture_types
    if room_id == session.room_id:
        session.fixture_types = fixture_types
    session.candidates_by_room[room_id] = []
    session.selected_candidates.pop(room_id, None)
    session.room_rationales.pop(room_id, None)
    session.sync_design_from_layouts()
    session.validation = []
    session.fixes = []
    session.applied_fixes = []
    session.stale = True
    _reset_sheet(session)
    session.ensure_plan(reset=True)
    session.add_decision(
        "fixtures_changed",
        room_id=room_id,
        previous=previous,
        fixtures=[fixture.value for fixture in fixture_types],
    )
    return {
        "room_id": room_id,
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
        f"Vent: {len(design.vent_pipes)} branch pipe(s); "
        f"stack {design.vent_stack.id if design.vent_stack else 'none'}.",
        f"Water: {len(design.supply_pipes)} hot/cold branch pipe(s); "
        f"source {design.water_source.id if design.water_source else 'none'}.",
        f"Equipment/valves: {len(design.plumbing_items)} item(s).",
        f"Validation: {counts['PASS']} PASS, {counts['WARNING']} WARNING, "
        f"{counts['ERROR']} ERROR.",
        "Sheet: "
        + (
            f"{session.sheet_pages} page(s), drawing review "
            f"{sheet_counts(session.drawing_review)['ERROR']} ERROR, "
            f"{sheet_counts(session.drawing_review)['WARNING']} WARNING."
            if session.sheet_ready
            else "not prepared."
        ),
        (
            "No automatic fix can clear the remaining validation errors. "
            "Remove a fixture, use a larger room, or ask for a different layout; "
            "export stays blocked until the errors are resolved."
            if counts["ERROR"] and not session.fixes
            else ""
        ),
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
    if not session.sheet_ready or not session.sheet_path:
        _prepare_sheet_tool({}, session)
    target = session.out_dir / f"{design.id}.dxf"
    target.write_bytes(Path(session.sheet_path).read_bytes())
    session.exported_path = str(target)
    return {
        "path": str(target),
        "pdf_path": session.sheet_pdf_path,
        "pages": session.sheet_pages,
        "drawing_counts": sheet_counts(session.drawing_review),
        "layers": [
            "P-SOIL",
            "P-WASTE",
            "P-VENT",
            "P-COLD",
            "P-HOT",
            "P-FIXTURE",
            "P-STACK",
            "P-DIM",
            "P-TITLE",
        ],
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
        "plan_room_layouts",
        "Generate and select the best valid layout for every selected room, "
        "producing one consolidated design.",
        _schema({}),
        _plan_room_layouts,
    )
)
_register(
    Tool(
        "select_layout",
        "Choose one generated layout for a room and record the engineering rationale.",
        _schema(
            {
                "room_id": {"type": "string"},
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
        "route_services",
        "Route fixture vents, hot/cold water supply, and add plumbing equipment, "
        "valves, cleanouts, and trap primers. Run after drainage routing.",
        _schema({}),
        _route_services,
    )
)
_register(
    Tool(
        "prepare_sheet",
        "Build or refresh the construction sheet: plan, riser diagram, blocks, "
        "dimensions, schedules, legend, notes, title block, SVG preview, and PDF.",
        _schema({}),
        _prepare_sheet_tool,
    )
)
_register(
    Tool(
        "set_sheet_options",
        "Set sheet size, orientation, scale, and content options. Presets: "
        + ", ".join([*SHEET_PRESETS_MM, "CUSTOM"])
        + ".",
        _schema(
            {
                "preset": {"type": "string"},
                "width_mm": {"type": "number"},
                "height_mm": {"type": "number"},
                "orientation": {
                    "type": "string",
                    "enum": ["landscape", "portrait"],
                },
                "scale": {"type": "number"},
                "include_riser": {"type": "boolean"},
                "include_schedules": {"type": "boolean"},
                "notes": {"type": "array", "items": {"type": "string"}},
            }
        ),
        _set_sheet_options,
    )
)
_register(
    Tool(
        "review_drawing",
        "Review the construction sheet for missing layers, blocks, dimensions, "
        "schedules, tags, title-block fields, viewports, and services.",
        _schema({}),
        _review_drawing,
    )
)
_register(
    Tool(
        "validate_design",
        "Validate drainage, vent, water supply, equipment, and code rules. Returns "
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
        "Return the current design state: fixtures, drainage, vent, hot/cold "
        "water, equipment, sheet/review status, validation, decisions, and plan.",
        _schema({}),
        _get_design_state,
    )
)
_register(
    Tool(
        "compare_layouts",
        "Compare all generated layouts for a room against the selected one, "
        "including deterministic rejection reasons.",
        _schema({"room_id": {"type": "string"}}),
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
                "room_id": {"type": "string"},
                "fixtures": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [item.value for item in FixtureType],
                    },
                },
            },
            ["fixtures"],
        ),
        _set_fixtures,
    )
)
_register(
    Tool(
        "export_dxf",
        "Export the approved construction sheet DXF. Requires explicit engineer "
        "approval and a clean drawing review.",
        _schema({}),
        _export_dxf,
        mutating=True,
    )
)


def tool_schemas() -> list[dict]:
    return [tool.schema() for tool in TOOLS.values()]
