# Flowline Design — Chat-First Workspace

**Status:** implemented 2026-10-30. This supersedes the earlier form-driven POC UI.

## Intent

Flowline is an agentic floor plumbing designer for AutoCAD-native workflows. It turns a DXF floor plan into one coordinated multi-room plumbing design with ranked room layouts, routed drainage, vent and water services, cited validation, deterministic fixes, and an AutoCAD-ready DXF. The LLM coordinates; deterministic Python owns the engineering.

This phase is deliberately **chat-first**. Home/project grouping is deferred; the workspace has one drawing and a designs list. Standards are per design, not per project.

## Consolidated floor design (2026-11-01)

- One `Design` can cover multiple selected rooms, with a `RoomPlan` per room and shared stacks, vents, water source, sheet, and schedules.
- Imported rooms are classified from labels plus plumbing-fixture block hints. Bathrooms, powder rooms, kitchens, balconies, utility areas, and wash areas are selected automatically; users can click the plan or room list to adjust.
- Drain-capable detected shafts are available as stacks. Each room is assigned to the nearest stack by default and can be reassigned in setup. Water- and vent-only shafts remain visible as service points.
- Shafts expose the services they carry (`DRAIN`, `WATER`, `VENT`). Drainage terminates at a drain or combined shaft, supply originates at a water or combined shaft, and vents use a vent or combined shaft.
- Detected source fixtures (WC, basin, shower, floor drain, kitchen sink) are exposed in the API and plan preview. A valid source arrangement is offered as the `existing` layout candidate; invalid arrangements remain visible as rejected alternatives.
- The design sheet covers the whole selected floor and includes a room column in the schedules and all stack risers.
- The legacy single-room request path remains supported; stored designs without room plans are normalized to one room.

## Decisions

- **Chat-first** instead of the old three-column form wizard.
- **React + Vite + TypeScript + Tailwind**, built into the FastAPI static directory.
- **Q&A + rerun/validate/fix.** The agent can inspect, compare, reselect layouts, revalidate with another standard, apply fixes, change the fixture set, and explain. No manual fixture dragging.
- **Per-design standards.** Changing the standard marks the design stale until revalidated.
- **Raw + structured visibility.** Show provider `reasoning_content` when available, interim agent notes otherwise, plus the plan, tool log, decisions, rejected layouts, validation and fix history.
- **JSON persistence.** Designs/messages/events survive restarts. Projects/home can layer on top.
- **Multi-turn agent.** Each user message is a turn with persisted state and compact conversation history; the model can re-query state rather than replaying old tool logs.

## Goals

- Start a design from a room, stack, fixture set and standard.
- Make the agent's plan, thinking/notes, tools, decisions, rejected alternatives and validation visible.
- Support follow-ups without losing the current design state.
- Persist everything locally in readable JSON.
- Keep the deterministic engine and approval gate unchanged.
- Ship a working demo for the hackathon.

## Non-goals (this pass)

- Home tab or project grouping; project-level standards.
- Manual fixture dragging or direct geometry editing.
- Water supply, vent geometry, PDF/image intake, Revit, DWG write.
- Multi-user/auth or cloud persistence.
- Full code compliance.

## UX

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ Flowline   drawing / room   [standard ▾]   [provider]   [Approve/export] │
├──────────────┬───────────────────────────────────────┬───────────────────┤
│ WORKSPACE    │ CHAT                                  │ PLAN + AGENT      │
│ drawing      │ user message                          │ plan preview      │
│ designs      │ plan stepper                          │ [Plan][Thinking]  │
│ + new design │ agent notes / reasoning               │ [Decisions]       │
│              │ tool timeline                         │ [Checks][Activity]│
│              │ candidate comparison                  │                   │
│              │ decisions / validation                │                   │
│              │ final answer                          │                   │
│              │ quick actions + composer              │                   │
└──────────────┴───────────────────────────────────────┴───────────────────┘
```

- **Workspace sidebar:** drawing upload/sample, designs list with status, new design, provider badge.
- **Setup:** plan preview, room, shaft or click-to-place stack, fixture chips, standard, start design.
- **Chat:** user/agent turns; quick actions Compare, Validate, Apply fix, Explain, Review & export.
- **Mission control:** Plan, Thinking, Decisions, Checks, Activity.
- **Approval dialog:** counts, warnings, stale/error blockers, approver, download.

## Agent

Tools: `inspect_plan`, `list_layout_options`, `select_layout`, `route_drainage`, `validate_design`, `apply_fix`, `set_fixtures`, `compare_layouts`, `get_design_state`, `explain_design`, `export_dxf`.

- `select_layout` records selected and rejected candidates with deterministic reasons.
- `route_drainage` records route failures.
- `validate_design` records profile changes and counts; marks the design not stale.
- `apply_fix` records before/after counts.
- `set_fixtures` resets the design and plan for a re-plan.
- `compare_layouts` supports follow-up questions.
- The loop emits `turn_start`, `plan`, `plan_update` (via plan events), `reasoning`, `assistant`, `tool_call`, `tool_result`, `decision`, `final`, `snapshot`.
- The provider parser captures `reasoning_content` (or `reasoning`/`thinking` aliases). If the provider returns no reasoning, interim assistant notes are shown instead.

## Persistence

```text
data/workspaces/<workspace_id>/
  workspace.json
  designs/<design_id>/
    design.json       # session state, candidates, validation, decisions, plan
    messages.json
    events.jsonl      # seq + turn_id; replay for reload
    audit.jsonl
    preview.svg
    export.dxf
```

Atomic JSON writes and one active turn per design. The API hydrates sessions from disk; in-memory caches are a performance layer.

## APIs

- `GET /api/projects`, `POST /api/projects/sample`, `POST /api/projects` upload.
- `GET /api/projects/{id}`, `GET /api/projects/{id}/designs`, `POST /api/projects/{id}/designs`.
- `POST /api/projects/{id}/design` (compatibility: create + first turn).
- `GET /api/designs/{id}` (state + messages + events), `/messages`, `/events`.
- `POST /api/designs/{id}/messages` (chat turn), `PATCH /api/designs/{id}` (standard).
- `POST /api/designs/{id}/fix`, `/approve`; `GET /download.dxf`, `/preview.svg`.
- `GET /api/jobs/{id}/events` SSE; `GET /api/jobs/{id}` polling.

## Standards

India NBC 2016 / IS 1742 (+ IPC clearances) and US IPC 2021, per design. Every validation result includes rule ID, measured/required, source and fix IDs. POC disclaimer everywhere.

## DXF understanding

- Layer roles classify walls, doors, windows, rooms, shafts and annotations.
- Shafts come from explicit shaft/duct/riser layers or labels, plus conservative inference from small solid hatches near wet rooms. Inferred shafts are labelled with a confidence and source.
- Nested sanitaryware block inserts are expanded in WCS and classified by block name, layer, dimensions and room context. Ambiguous blocks remain sanitaryware hints rather than being mislabelled.
- Closed room polylines are used directly. Wall-line plans fall back to centreline extraction with collinear gap bridging, T-junction connectors and Shapely polygonization.
- Room labels are matched to polygons; dimension notes and title text are rejected.
- Block inserts are expanded with layer inheritance, so door/window blocks contribute real geometry.
- Preview extents cover plan geometry only; title blocks, dimensions and notes are hidden.
- A drawing with no shaft can use a user-picked stack point.

## Constraints

- Python 3.13, Windows dev, React/Vite build, no AutoCAD required for tests. Shapely/GEOS is required for wall-based room extraction.
- Meta/OpenCode/OpenRouter providers; fake offline provider.
- Local single-user JSON data.
- Hackathon deadline 2026-11-04.

## Risks

- Provider reasoning availability varies; agent notes + structured decisions compensate.
- Chat latency/cost: compact prompts, one turn at a time, deterministic tools.
- JSON concurrency: atomic writes and locks; local only.
- Scope: projects/home deferred; manual editing deferred.
- Demo reproducibility: fake provider smoke + real provider manual run.

## Next phase

Home + projects (multiple drawings, project standards), manual fixture placement, water supply/venting, PDF/image intake, AutoCAD LT/.NET plugin, Revit/IFC, rule-pack authoring and sign-off.
