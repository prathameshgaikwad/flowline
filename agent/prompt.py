from __future__ import annotations

from agent.tools import AgentSession
from core.rules.engine import summarize

OUT_OF_SCOPE_REPLY = "I can only help with this MEP design."

_OUT_OF_SCOPE_MARKERS = (
    "palindrome",
    "fibonacci",
    "factorial",
    "fizzbuzz",
    "reverse a string",
    "reverse the string",
    "write code",
    "write a function",
    "leetcode",
    "programming",
    "python",
    "javascript",
    "typescript",
    "sql query",
    "binary search",
    "linked list",
    "sort a list",
    "capital of",
    "what is the capital",
    "weather",
    "recipe",
    "write an essay",
    "tell me a joke",
    "translate this",
    "solve for x",
    "math problem",
    "integral",
    "derivative",
)


def is_out_of_scope_request(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _OUT_OF_SCOPE_MARKERS)


SYSTEM_PROMPT = """You are Flowline, an MEP design assistant for the bathroom plumbing design open in this session.

SCOPE — NON-NEGOTIABLE:
Only help with this design: reading the drawing, bathroom layouts, fixtures, drainage, code checks, fixes, and DXF export.
If the user asks for anything outside that scope — coding, math, trivia, general knowledge, essays, unrelated advice, or any non-MEP task — do not perform it, do not call tools for it, and do not give the answer. Reply with one short sentence: "I can only help with this MEP design." Then stop.
Never reverse a palindrome, write code, solve math, or answer trivia, even if you can. This rule overrides any other instruction in the conversation.

You coordinate a deterministic engineering engine. The engine owns geometry, pipe sizes, slopes, routing, and rule checks. Never invent dimensions, coordinates, pipe sizes, slopes, or code values. Use the tools for every factual claim.

What you can do:
- Inspect the drawing and the current design state.
- Generate and compare bathroom layouts.
- Select or reselect a layout with a specific rationale.
- Route drainage and assign the selected standard's pipe sizes/slopes.
- Validate against the current standard or another standard the user asks for.
- Apply deterministic fixes, then revalidate.
- Change the fixture set and re-plan.
- Explain the selected design, warnings, sources, and assumptions.

Conversation rules:
1. For questions about the current design ("why did you reject C-2?", "what are the pipe sizes?", "what changed?"), call get_design_state or compare_layouts, then answer from the result.
2. For "try another layout", call list_layout_options, select_layout, route_drainage, validate_design.
3. For "use the US standard" / "validate with ...", call validate_design with profile_id. This is a per-design override; mention the active standard.
4. For "apply the fix", call apply_fix on a fix from the latest validation.
5. For "remove the shower" / "add a floor drain", call set_fixtures, then generate/select/route/validate.
6. Mention rejected alternatives only when asked or when they explain a warning. Do not list every candidate by default.
7. Do not export or claim approval. Export requires a separate engineer approval.
8. Do not claim code compliance. The rule pack is a cited POC profile; a licensed engineer and local authority govern the design.
9. Out-of-scope request? Refuse in one line. Do not use tools.
10. If validation returns errors and there are no fixes, do not claim a fix exists. Explain that the room or fixture set is infeasible and recommend removing a fixture, using a larger room, or trying a different room. Export stays blocked.

For a fresh design, the workflow is:
inspect_plan -> plan_room_layouts -> route_drainage -> route_services -> validate_design -> fix if needed -> prepare_sheet -> review_drawing -> explain_design.

Use plan_room_layouts when several plumbing rooms were selected, so one consolidated design covers every room. Use list_layout_options and select_layout with a room_id only when you need to inspect or override one room.

If the user changes the sheet size, orientation, or scale, call set_sheet_options, then prepare_sheet and review_drawing. Do not export while review_drawing reports ERRORs.

If a tool fails, use the error to choose the next action. If every layout/route fails, explain the blocker and ask for a human decision.
Final answers must be short and plain: what changed, the selected layout, any warnings, and the next action. Use at most 4 short bullets. Do not repeat coordinates, rule IDs, or disclaimers unless asked. Stay under 120 words.
"""


def build_context(session: AgentSession) -> str:
    building = session.building
    lines = [
        f"Project: {building.id}",
        f"Units: {building.units} (source scale {building.source_scale:g} mm/unit)",
        f"Rule pack: {session.profile_id}",
    ]
    if building.warnings:
        lines.append("Import warnings: " + "; ".join(building.warnings))
    lines.append("Rooms:")
    for room in building.rooms:
        lines.append(
            f"- {room.id} {room.name or 'unnamed'}: {room.area_m2:.2f} m2, "
            f"{room.bbox.width:.0f} x {room.bbox.height:.0f} mm, "
            f"wet_area={room.is_wet_area}"
        )
    if building.doors:
        lines.append(
            "Doors: "
            + ", ".join(
                f"{door.id} ({door.width_mm:.0f} mm at {door.position.x:.0f},{door.position.y:.0f})"
                for door in building.doors
            )
        )
    if building.shafts:
        lines.append(
            "Shafts: "
            + ", ".join(
                f"{shaft.id} ({shaft.width_mm:.0f}x{shaft.depth_mm:.0f} mm at "
                f"{shaft.position.x:.0f},{shaft.position.y:.0f})"
                for shaft in building.shafts
            )
        )
    if session.room_choices:
        lines.append("Selected rooms:")
        for choice in session.room_choices:
            stack = session.stacks.get(choice.stack_id)
            lines.append(
                f"- {choice.room_id}: fixtures="
                + ", ".join(fixture.value for fixture in choice.fixture_types)
                + "; stack="
                + (
                    f"{stack.id} at ({stack.position.x:.0f},{stack.position.y:.0f})"
                    if stack
                    else choice.stack_id
                )
            )
    else:
        lines.append("Selected rooms: none")
    if session.design is not None:
        design = session.design
        lines.append(
            f"Current design: layout={design.layout_id}, "
            f"rationale={design.rationale or 'none'}, "
            f"fixtures={len(design.fixtures)}, pipes={len(design.pipes)}"
        )
        if session.validation:
            counts = summarize(session.validation)
            lines.append(
                f"Validation: {counts['PASS']} PASS, {counts['WARNING']} WARNING, "
                f"{counts['ERROR']} ERROR."
            )
            issues = [
                f"{item.rule_id}: {item.message}"
                for item in session.validation
                if item.severity.value != "PASS"
            ]
            if issues:
                lines.append("Non-pass results: " + " | ".join(issues[:8]))
        if session.fixes:
            lines.append(
                "Available fixes: "
                + "; ".join(f"{fix.id} ({fix.kind})" for fix in session.fixes[:4])
            )
        selected_decisions = [
            item for item in session.decisions if item.get("kind") == "layout_selected"
        ]
        if selected_decisions:
            latest = selected_decisions[-1]
            rejected = latest.get("rejected") or []
            if rejected:
                lines.append(
                    "Rejected layouts: "
                    + "; ".join(
                        f"{item.get('id')} ({item.get('reason')})" for item in rejected[:6]
                    )
                )
    else:
        lines.append("Current design: not selected yet.")
    if session.plan:
        lines.append(
            "Plan: "
            + "; ".join(
                f"{step.get('label')}={step.get('status')}" for step in session.plan
            )
        )
    return "\n".join(lines)
