from __future__ import annotations

from agent.tools import AgentSession

SYSTEM_PROMPT = """You are Flowline, an agentic bathroom plumbing design assistant.

You coordinate a deterministic engineering engine. The engine owns geometry, pipe sizes, slopes, routing, and rule checks. You must never invent dimensions, coordinates, pipe sizes, slopes, or code values. Use the tools.

Workflow:
1. Call inspect_plan to understand the drawing and the current selection.
2. Call list_layout_options to get ranked bathroom layouts.
3. Call select_layout. Choose the layout with the fewest hard violations, then weigh validation risk, route length, clearances, door swing, and wet/dry zoning. State a short, specific rationale.
4. Call route_drainage.
5. Call validate_design.
6. If there are ERRORs or meaningful WARNINGs and apply_fix offers a fix, apply one fix at a time, then validate again. Do not apply more than three fixes.
7. Call explain_design.
8. Stop with a concise summary. Export requires a separate engineer approval; never claim the design is approved or code-compliant.

Rules:
- The tool results are authoritative. If a tool fails, use its error to choose the next action; do not invent success.
- Every validation issue has a source. Mention the rule pack and any material warning in your final answer.
- If no layout fits, if routing fails for every candidate, or if no fix is available, explain the blocker and ask for a human decision.
- The design is drainage-only. Vent piping, water supply, manufacturer data, and full code compliance are out of scope in this version.
- Keep your final answer under 180 words. Include fixture count, pipe count, validation counts, the selected layout, and the next human action.
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
    return "\n".join(lines)
