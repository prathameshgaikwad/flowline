# Flowline Design

**Status:** Hackathon MVP design, approved 2026-10-29.

## Intent

Flowline is an agentic bathroom plumbing designer. It turns a DXF floor plan into ranked wet-area layouts, routed drainage, cited validation, deterministic fixes, and an AutoCAD-ready DXF. The LLM coordinates; deterministic engines own geometry, sizing, and rules.

The first customer is a small MEP consultancy or design-build contractor that draws repetitive bathroom drainage in AutoCAD and cannot justify a full BIM/calculation suite. The wedge is intentionally narrow: one bathroom, one stack, drainage only, two rule packs.

## Why now

- "Agentic MEP" is an emerging category (for example WYRM) built on a clear boundary: agents coordinate, deterministic engines calculate, a named engineer signs.
- Small firms still redraw the same wet-area layouts by hand; mistakes surface late in coordination.
- Meta Muse Spark's tool calling makes a multi-step design-review-fix loop practical without letting a language model invent engineering values.

## Goals

- Upload a clean DXF plan; detect rooms, doors, shafts, and units.
- Generate at least three deterministic bathroom layouts.
- Let the agent select a layout with a written tradeoff rationale.
- Route each fixture to a stack with orthogonal, obstacle-aware paths.
- Validate against an India profile and a US profile, each with citations.
- Apply deterministic fixes and revalidate.
- Preview as SVG and export an overlaid DXF that opens in AutoCAD.
- Keep all engineering math outside the LLM.
- Record an audit trail of model, provider, tools, inputs, and results.

## Non-goals

- Code compliance certification or permit drawings.
- Full MEP coordination, HVAC, electrical, water supply, or vent design.
- Revit, IFC, 3D, multi-floor, DWG writing, or cost estimation.
- Universal DXF parsing. v1 supports clean plans and offers manual fallback.

## Anti-goals

- The LLM computing dimensions, pipe sizes, slopes, or rule outcomes.
- Silent edits to a drawing.
- Claiming a standard has been satisfied when it has only been checked against a small profile.
- Reusing pre-hackathon source code.
- Writing to arbitrary model-supplied file paths.

## Approaches considered

1. **Generated candidates + agent selection (chosen).** Deterministic patterns generate valid layouts; the agent chooses and explains. Reliable, explainable, and visibly agentic.
2. **User places fixtures; agent routes and validates.** Fastest to build, but more drafting assistant than designer. Kept as a manual override idea.
3. **LLM places fixtures directly.** Rejected: unreliable geometry, slow, hard to demo.
4. **Revit-first integration.** Rejected for the hackathon: no Revit installed and too much integration work. Revit is a later product path.
5. **Live AutoCAD-first.** Rejected as the core: COM is single-threaded and version-sensitive. Headless DXF is the reliable demo; live AutoCAD is a stretch.

## Architecture

```text
Browser (SVG, agent trace, validation, approval)
        |
FastAPI + SSE jobs
        |
Agent loop ---- provider factory
        |         |-- MetaProvider (muse-spark-1.3)
        |         |-- OpenRouterProvider
        |         |-- FakeProvider
        |
Deterministic tools
        |-- inspect_plan
        |-- list_layout_options
        |-- select_layout
        |-- route_drainage
        |-- validate_design
        |-- apply_fix
        |-- explain_design
        |-- export_dxf (approval-gated)
        |
Core engine
        |-- DXF import/export
        |-- geometry + units
        |-- layout generator
        |-- A* router
        |-- cited rule packs
        |-- deterministic fixes
        |-- SVG renderer
```

## Data flow

1. DXF is imported into a millimetre `Building` with rooms, doors, shafts, labels, and background entities.
2. The user selects a room, stack, fixture set, and rule profile.
3. The layout generator returns ranked `LayoutCandidate`s.
4. The agent selects one and records its rationale.
5. The router creates `Pipe`s with system, diameter, slope, from/to nodes, and geometry.
6. The validator returns `ValidationResult`s with rule IDs, citations, measured/required values, and fix IDs.
7. The fix engine applies deterministic changes; the agent revalidates.
8. On approval, the exporter overlays `P-*` layers on the source DXF.

## Domain model

- `Building`: units, source scale, rooms, doors, shafts, background entities, warnings.
- `Room`: polygon boundary, name, area, bounding box.
- `Fixture`: type, position, rotation, footprint, drain point, room.
- `Pipe`: system, diameter, slope, points, from/to nodes.
- `Stack`: position, diameter.
- `Design`: room, profile, fixtures, pipes, stacks, selected layout, rationale, assumptions.
- `ValidationResult`: rule, severity, message, source, measured, required, affected, fixes.
- `Fix`: kind, description, affected, parameters.

## Algorithms

### Layout generation

Pattern families: wet wall, side-by-side, L-shape, corner shower, split. For each pattern and wall orientation, the generator places fixtures on wall offsets, checks footprints, side/front clearances, fixture spacing, door swing, stack, and room containment. Candidates are scored by hard violations first, then route length, bends, comfort clearances, and wet/dry zoning. Output is deterministic and deduplicated.

### Routing

Orthogonal A* on a 100 mm grid inside the room and shaft corridor. Fixtures and walls are inflated obstacles; the stack cell is free. The path is simplified to turns. Plan length and invert drop are recorded with the slope.

### Validation

Data-driven profiles define room minimums, fixture clearances, pipe sizes, slopes, stack sizes, fixture units, and vent warnings. The engine returns PASS/WARNING/ERROR with a citation for every rule. It never converts a warning into a pass.

### Fixes

`SELECT_CANDIDATE`, `REROUTE_PIPE`, `ADJUST_SLOPE`, and `CHANGE_PIPE_SIZE` are deterministic and bounded. A fix returns a new design state and a reason. The agent can apply at most three fixes before reporting a blocker.

## Agent design

The agent receives a compact plan summary and the selected profile. It must inspect the plan, list layouts, select one, route, validate, fix errors, explain, and stop. Tool calls are strict JSON. Unknown tools, invalid candidates, and blocked exports return structured errors. The loop has a maximum iteration count and a repeat-call guard.

Provider strategy:

```text
LLM_PROVIDER=auto (default)
  META_API_KEY or MODEL_API_KEY -> MetaProvider
  OPENROUTER_API_KEY            -> OpenRouterProvider
  otherwise                     -> FakeProvider
```

Explicit `meta`, `openrouter`, or `fake` overrides auto. An explicit provider without its key fails fast.

## Interfaces

- CLI: `python scripts/demo_cli.py --provider fake|meta|openrouter --sample samples/apartment.dxf`.
- Web: `python -m uvicorn app.main:app --reload`.
- Manual provider check: `python scripts/check_provider.py`.
- Export: `out/<project>/design.dxf`, `design.json`, `preview.svg`, `audit.jsonl`.

## Constraints

- Python 3.13, Windows development, no AutoCAD required for tests.
- Meta Model API credits and key are supplied by the user.
- Standards are summarized and cited, not reproduced.
- Public repo; no secrets; no pre-event code.
- Hackathon deadline: 2026-11-04 21:00 ET.

## What is left to the builder

- Exact fixture footprints and comfort targets (pinned in `core/fixtures.py`).
- Exact wall-offset search strategy and tie-breaking.
- SVG visual style and UI layout.
- Whether live AutoCAD is stable enough for the video.

## Product path after the hackathon

1. Harden DXF intake (legacy polylines, blocks, xrefs, layers, PDF/image via Muse vision).
2. Add water supply, vent, kitchen, multi-room and multi-floor design.
3. Add rule-pack authoring, project versions, engineer sign-off, and BOQ.
4. Integrate AutoCAD LT plugin/COM, then Revit/IFC and APS.
5. Sell per seat plus metered drawing automation to small MEP firms in India/MENA, then UK/US.

## Risks

- DXF variability: clean-plan scope and manual fallback.
- Meta tool reliability: strict schemas, deterministic tools, bounded loop, fake fallback for development.
- Standards accuracy: small cited subset, disclaimers, conservative ranges.
- Time: MVP first; drop live AutoCAD and image intake before core functionality.
