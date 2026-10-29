# Flowline Bathroom Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a new, public, hackathon-eligible agentic bathroom plumbing designer that turns a DXF floor plan into ranked layouts, routed drainage, cited validation, deterministic fixes, and an AutoCAD-ready DXF export, driven by Meta Muse Spark.

**Architecture:** A FastAPI web app and CLI sit above an agent loop. The LLM only selects deterministic tools. A Python core owns DXF import, geometry, layout generation, A* routing, rule profiles, fixes, SVG, and DXF export. Providers are chosen by a strategy factory (Meta > OpenRouter > Fake).

**Tech Stack:** Python 3.13, FastAPI, Uvicorn, Pydantic 2, ezdxf 1.4, PyYAML, python-dotenv, pytest, httpx, Playwright, vanilla HTML/CSS/JS + SVG.

**Spec:** `docs/design.md` and `docs/standards.md`

## Global Constraints

- New public repo, first commit during the hackathon; no pre-event code copied.
- Internal units are millimetres everywhere.
- The LLM never computes geometry, sizes, slopes, or rule outcomes.
- Every validation result names a rule ID and a source citation.
- Never claim code compliance; always show the engineer/local-authority disclaimer.
- Export is approval-gated and must preserve the source drawing.
- Secrets live only in `.env`; never log or commit keys.
- Meta model id default: `muse-spark-1.3`; Meta base URL: `https://api.meta.ai/v1`.
- Provider precedence: explicit `LLM_PROVIDER`, else Meta key, else OpenRouter key, else fake.
- Deadline: submit before Nov 4, 9 PM ET; internal target Nov 3 evening IST.

## Review Focus

- A unitless or metre-based DXF must not silently scale the design wrong; it must convert or warn.
- An open or unsupported room boundary must produce a clear manual fallback, never a crash.
- A layout with a door swing or fixture overlap must be rejected before routing.
- A pipe route must not cross a fixture footprint or leave the room/shaft corridor.
- A missing Meta key must fail visibly, not silently fall back during the live demo.

---

### Task 1: Repo scaffold, configuration, provider factory

**Files:**
- Create: `.gitignore`, `.env.example`, `requirements.txt`, `pyproject.toml`, `README.md`, `LICENSE`
- Create: `core/__init__.py`, `agent/__init__.py`, `agent/providers/__init__.py`
- Create: `agent/providers/base.py`, `agent/providers/factory.py`, `agent/providers/fake.py`
- Test: `tests/test_provider_factory.py`

**Interfaces:**
- Produces: `LLMProvider` protocol with `name`, `model`, `chat(messages, tools) -> LLMResponse`.
- Produces: `create_provider(env: Mapping[str, str]) -> LLMProvider`.
- Produces: `FakeProvider` with a scripted `ToolCall` trajectory for tests.

- [ ] Write `tests/test_provider_factory.py` covering: Meta key wins when both keys exist; OpenRouter wins when only that key exists; explicit `fake` wins; explicit `meta` without key raises `ConfigError`; no keys returns Fake.
- [ ] Run `pytest tests/test_provider_factory.py -v` and confirm failure.
- [ ] Implement `agent/providers/base.py` (`ChatMessage`, `ToolCall`, `LLMResponse`, `LLMError`, `ConfigError`, `LLMProvider`) and `factory.py`.
- [ ] Run the tests; confirm pass.
- [ ] Commit: `feat: add provider strategy and project scaffold`.

### Task 2: Units, geometry, and domain models

**Files:**
- Create: `core/units.py`, `core/geometry.py`, `core/models.py`, `core/fixtures.py`
- Test: `tests/test_units.py`, `tests/test_geometry.py`, `tests/test_models.py`

**Interfaces:**
- Produces: `Units`, `unit_scale_to_mm(insunits: int) -> tuple[float, Units, list[str]]`.
- Produces: `Point`, `Room`, `Door`, `Shaft`, `Building`, `FixtureType`, `Fixture`, `Pipe`, `Stack`, `Design`, `ValidationResult`, `Fix`.
- Produces: geometry helpers `polygon_area`, `point_in_polygon`, `bbox`, `rect_corners`, `rects_overlap`, `inflate_rect`, `segment_intersects_rect`.

- [ ] Write failing tests for mm/metre/inch conversion, polygon area/containment, rectangle overlap, fixture footprint lookup, and room area.
- [ ] Run tests; confirm failure.
- [ ] Implement the modules with Pydantic v2 models and pure helpers.
- [ ] Run tests; confirm pass.
- [ ] Commit: `feat: add units, geometry, and domain models`.

### Task 3: DXF import and sample plan generator

**Files:**
- Create: `core/dxf_import.py`, `scripts/make_sample_plan.py`
- Create: `samples/apartment.dxf`, `samples/tight_bathroom.dxf`
- Test: `tests/test_dxf_import.py`

**Interfaces:**
- Produces: `import_dxf(path: str | Path) -> Building`.
- Produces: `Building.warnings: list[str]`, `Building.source_scale: float`, `Building.entities: list[DrawingEntity]`.
- Produces: two sample DXFs in millimetres with rooms, door, shaft, labels.

- [ ] Write failing tests: sample apartment imports rooms/doors/shafts/labels; metre-based DXF converts to mm; unitless warns; open polyline is not a room; unsupported entities do not crash.
- [ ] Run tests; confirm failure.
- [ ] Implement sample generator and importer (closed LWPOLYLINE/POLYLINE rooms, text labels, INSERT/layer doors, shaft layers/text, `$INSUNITS`).
- [ ] Generate and commit samples.
- [ ] Run tests; confirm pass.
- [ ] Commit: `feat: import DXF floor plans and generate samples`.

### Task 4: SVG preview renderer

**Files:**
- Create: `core/svg.py`
- Test: `tests/test_svg.py`

**Interfaces:**
- Produces: `render_svg(building: Building, design: Design | None = None, width: int = 1200) -> str`.
- Produces: layer colors, room fills, fixture/pipes/stack overlays, and a stable `viewBox`.

- [ ] Write failing tests: SVG contains room polygons, door marker, shaft, fixture rectangles, pipe polyline, stack circle, and an XML-parseable document.
- [ ] Run tests; confirm failure.
- [ ] Implement the renderer with coordinate mapping that keeps text upright.
- [ ] Run tests; confirm pass.
- [ ] Commit: `feat: render plan and design as SVG`.

### Task 5: Layout candidate generator

**Files:**
- Create: `core/layout.py`
- Test: `tests/test_layout.py`

**Interfaces:**
- Produces: `generate_layouts(building: Building, room_id: str, fixture_types: list[FixtureType], stack: Point, profile: RuleProfile) -> list[LayoutCandidate]`.
- Produces: `LayoutCandidate(id, pattern, fixtures, score, violations, rationale_hint)`.
- Guarantees: deterministic ordering; at least 3 candidates for the sample bathroom; no fixture overlaps.

- [ ] Write failing tests: sample room produces >= 3 candidates; every candidate has WC/BASIN/SHOWER; no overlapping footprints; door zone rejected; tight room yields a violation or a clear infeasible result.
- [ ] Run tests; confirm failure.
- [ ] Implement rectangle wall patterns, wall offsets, clearance checks, scoring, and deduplication.
- [ ] Run tests; confirm pass.
- [ ] Commit: `feat: generate deterministic bathroom layouts`.

### Task 6: Orthogonal A* router

**Files:**
- Create: `core/router.py`
- Test: `tests/test_router.py`

**Interfaces:**
- Produces: `route_pipes(building, design, profile) -> list[Pipe]`.
- Guarantees: every pipe starts at a fixture drain point, ends at the stack, stays inside the room/shaft corridor, avoids other fixture footprints.

- [ ] Write failing tests: route from each fixture to the stack; path avoids an obstacle; path is orthogonal; route inside a 100 mm grid; no path returns a structured error.
- [ ] Run tests; confirm failure.
- [ ] Implement grid A*, bend penalty, path simplification, slope metadata.
- [ ] Run tests; confirm pass.
- [ ] Commit: `feat: route drainage with orthogonal A*`.

### Task 7: Rule packs and validator

**Files:**
- Create: `core/rules/__init__.py`, `core/rules/engine.py`
- Create: `core/rules/profiles/india_nbc_2016.yaml`, `core/rules/profiles/us_ipc_2021.yaml`
- Create: `core/rules/citations.md`
- Test: `tests/test_rules.py`

**Interfaces:**
- Produces: `load_profile(profile_id: str) -> RuleProfile`.
- Produces: `validate_design(building, design, profile) -> list[ValidationResult]`.
- Rule IDs are stable and each result includes `source`, `measured`, `required`, `fix_ids`.

- [ ] Write failing tests for each rule family: room size, WC side/front clearance, fixture spacing, shower size, pipe diameter, slope, connectivity, pipe containment, door clearance, stack size.
- [ ] Run tests; confirm failure.
- [ ] Implement the YAML profiles, loader, and checks; include PASS/WARNING/ERROR.
- [ ] Run tests for both profiles; confirm pass.
- [ ] Commit: `feat: add cited India and US rule packs`.

### Task 8: Deterministic fix engine

**Files:**
- Create: `core/fixes.py`
- Test: `tests/test_fixes.py`

**Interfaces:**
- Produces: `list_fixes(design, validation) -> list[Fix]`.
- Produces: `apply_fix(design, fix, profile) -> Design`.
- Supports: `SELECT_CANDIDATE`, `REROUTE_PIPE`, `ADJUST_SLOPE`, `CHANGE_PIPE_SIZE`.

- [ ] Write failing tests: a clearance error produces a candidate-switch fix; apply it and revalidate; a route error produces a reroute fix; slope and size fixes stay inside the profile.
- [ ] Run tests; confirm failure.
- [ ] Implement fixes with bounded, deterministic behavior.
- [ ] Run tests; confirm pass.
- [ ] Commit: `feat: add deterministic design fixes`.

### Task 9: Agent tools, prompt, and loop

**Files:**
- Create: `agent/tools.py`, `agent/prompt.py`, `agent/loop.py`, `agent/logging.py`
- Test: `tests/test_agent_tools.py`, `tests/test_agent_loop.py`

**Interfaces:**
- Produces tools: `inspect_plan`, `list_layout_options`, `select_layout`, `route_drainage`, `validate_design`, `apply_fix`, `explain_design`, `export_dxf`.
- Produces: `AgentRunner.run(request, session) -> AgentResult` with events callback.
- Produces: JSONL audit log with provider/model/tool/duration.

- [ ] Write failing tests: tool schemas are valid JSON Schema; unknown tool returns structured error; selection requires a valid candidate; dry-run blocks export; loop stops on repeated calls; fake provider completes E2E.
- [ ] Run tests; confirm failure.
- [ ] Implement tools, prompt, loop, and audit logging.
- [ ] Run tests; confirm pass.
- [ ] Commit: `feat: add agent tools and tool-calling loop`.

### Task 10: Meta and OpenRouter providers

**Files:**
- Create: `agent/providers/chat_completions.py`, `agent/providers/meta.py`, `agent/providers/openrouter.py`, `scripts/check_provider.py`
- Test: `tests/test_providers.py`

**Interfaces:**
- Produces: `ChatCompletionsProvider(base_url, api_key, model, name, headers)`.
- Produces: `MetaProvider`, `OpenRouterProvider`.
- Produces: `scripts/check_provider.py` that lists models and runs one tiny tool call without printing keys.

- [ ] Write failing tests with mocked HTTP: payload shape; tool-call parsing; HTTP error normalization; timeout; retry on 429; Meta defaults.
- [ ] Run tests; confirm failure.
- [ ] Implement the client and subclasses.
- [ ] Run tests; confirm pass.
- [ ] Run `scripts/check_provider.py` live with the Meta key when available.
- [ ] Commit: `feat: add Meta and OpenRouter providers`.

### Task 11: CLI end-to-end demo

**Files:**
- Create: `scripts/demo_cli.py`
- Test: `tests/test_e2e.py`

**Interfaces:**
- Produces: one command that imports a sample, generates layouts, runs the agent, validates, applies fixes, and writes `out/design.dxf`, `out/design.json`, `out/preview.svg`, `out/audit.jsonl`.

- [ ] Write failing test: run the pipeline with FakeProvider; assert 0 errors, 3 fixtures, 3 pipes, parseable DXF, audit lines.
- [ ] Run test; confirm failure.
- [ ] Implement the script.
- [ ] Run test and the command; confirm pass.
- [ ] Commit: `feat: add end-to-end CLI demo`.

### Task 12: FastAPI app, jobs, SSE

**Files:**
- Create: `app/__init__.py`, `app/main.py`, `app/jobs.py`, `app/schemas.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Endpoints: `GET /api/health`, `POST /api/projects`, `POST /api/projects/sample`, `GET /api/projects/{id}`, `POST /api/projects/{id}/design`, `GET /api/jobs/{id}/events`, `POST /api/designs/{id}/fix`, `POST /api/designs/{id}/approve`, `GET /api/designs/{id}/download.dxf`, `GET /api/profiles`.
- Produces: job events with `status`, `tool_call`, `tool_result`, `candidate`, `validation`, `final`, `error`.

- [ ] Write failing tests with TestClient and FakeProvider: upload sample, start design, read events, approve, download; reject traversal paths; block export with errors.
- [ ] Run tests; confirm failure.
- [ ] Implement the API, job manager, and SSE.
- [ ] Run tests; confirm pass.
- [ ] Commit: `feat: add web API with streaming agent trace`.

### Task 13: Web UI

**Files:**
- Create: `app/static/index.html`, `app/static/styles.css`, `app/static/app.js`
- Test: `scripts/ui_smoke.py` (Playwright)

**Interfaces:**
- Produces: upload/sample flow, room/stack/fixture/profile selection, live trace, candidate cards, validation citations, apply-fix, approve, download, before/after.

- [ ] Write the Playwright smoke test against the running app with FakeProvider.
- [ ] Run it; confirm failure.
- [ ] Implement the UI.
- [ ] Run smoke test; confirm pass and capture screenshots.
- [ ] Commit: `feat: add Flowline web interface`.

### Task 14: DXF export, live AutoCAD, docs, submission

**Files:**
- Create: `core/dxf_export.py`, `scripts/send_to_autocad.py`
- Update: `README.md`, `docs/design.md`, `docs/standards.md`, `docs/demo-script.md`
- Test: `tests/test_dxf_export.py`

**Interfaces:**
- Produces: `export_design(building, design, source_path, target_path) -> str` preserving source entities and adding `P-*` layers.
- Produces: `send_to_autocad.py --dxf path` that opens the drawing in a running AutoCAD 2024 instance.

- [ ] Write failing tests: export reopens; source entities preserved; design layers present; source units restored.
- [ ] Run test; confirm failure.
- [ ] Implement export and the AutoCAD script.
- [ ] Run test and open the exported file in AutoCAD.
- [ ] Write the 3-minute demo script; record; update README; verify public repo; submit.
- [ ] Commit: `docs: finalize hackathon submission`.

## Self-Review

- Spec coverage: import, layouts, routing, rules, fixes, agent, providers, UI, export, tests, demo, submission.
- Type consistency: `Design`, `LayoutCandidate`, `ValidationResult`, and `Fix` are introduced before use; tool interfaces match core signatures.
- Review focus tests are owned by Tasks 2, 3, 5, 6, and 10.
- Uncovered but accepted for v1: non-rectangular rooms, PDF/image intake, water supply/vent design, DWG write, Revit, live COM inside the web server.
