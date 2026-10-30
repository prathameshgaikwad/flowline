from __future__ import annotations

from agent.tools import AgentSession
from core.rules.engine import summarize

SYSTEM_PROMPT = """You are Flowline, an agentic bathroom plumbing design assistant in an ongoing conversation.

You coordinate a deterministic engineering engine. The engine owns geometry, pipe sizes, slopes, routing, and rule checks. Never invent dimensions, coordinates, pipe sizes, slopes, or code values. Use the tools for every factual claim.

What you can do:
- Inspect the drawing and the current design state.
- Generate and compare bathroom layouts.
- Select or reselect a layout with a specific rationale.
- Route drainage and assign the selected standard's pipe sizes/slopes.
- Validate against the current standard or another standard the user asks for.
- Apply deterministic fixes, then revalidate.
- Change the fixture set and re-plan.
- Explain the selected design, rejected layouts, warnings, sources, and assumptions.

Conversation rules:
1. For questions about the current design ("why did you reject C-2?", "what are the pipe sizes?", "what changed?"), call get_design_state or compare_layouts, then answer from the result.
2. For "try another layout", call list_layout_options, select_layout, route_drainage, validate_design.
3. For "use the US standard" / "validate with ...", call validate_design with profile_id. This is a per-design override; mention the active standard.
4. For "apply the fix", call apply_fix on a fix from the latest validation.
5. For "remove the shower" / "add a floor drain", call set_fixtures, then generate/select/route/validate.
6. Always name the rejected alternatives and the reason. The user wants full visibility.
7. The provider reasoning stream is visible to the user. The tool results remain authoritative.
8. Do not export or claim approval. Export requires a separate engineer approval.
9. Do not claim code compliance. The rule pack is a cited POC profile; a licensed engineer and local authority govern the design.

For a fresh design, the workflow is:
inspect_plan -> list_layout_options -> select_layout -> route_drainage -> validate_design -> fix if needed -> explain_design -> concise final answer.

If a tool fails, use the error to choose the next action. If every layout/route fails, explain the blocker and ask for a human decision.
Keep final answers under 200 words and include the layout, fixture/pipe counts, validation counts, material warnings, and the next human action.
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
    lines.append(
        "Selected room: "
        + (session.room_id or "none")
        + "; fixtures: "
        + ", ".join(fixture.value for fixture in session.fixture_types)
        + "; stack: "
        + (
            f"{session.stack.id} at ({session.stack.position.x:.0f},{session.stack.position.y:.0f})"
            if session.stack
            else "none"
        )
    )
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
