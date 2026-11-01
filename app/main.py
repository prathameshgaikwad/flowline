from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

import config  # noqa: F401  (loads .env)
from agent.logging import ActionLogger
from agent.loop import AgentRunner
from agent.providers.base import ChatMessage, ConfigError
from agent.providers.factory import create_provider
from agent.tools import TOOLS, AgentSession, RoomChoice, ToolError
from app import storage
from app.jobs import Job, JobManager
from app.models import Project
from app.schemas import (
    ApproveRequest,
    DesignRequest,
    FixRequest,
    MessageRequest,
    ProfileRequest,
    RoomSelection,
    SheetRequest,
)
from core.consolidated import (
    nearest_stack,
    stacks_for_building,
    water_sources_for_building,
)
from core.dxf_import import DxfImportError, import_dxf
from core.fixes import FixError, apply_fix, recommend_fixes
from core.models import Building, Severity, Stack
from core.plumbing import build_plumbing
from core.router import RouteError
from core.rules.engine import (
    available_profiles,
    load_profile,
    summarize,
    validate_design,
)
from core.svg import render_svg

ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR = ROOT / "samples"
STATIC_DIR = Path(__file__).resolve().parent / "static"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024

PROJECTS: dict[str, Project] = {}
DESIGNS: dict[str, AgentSession] = {}
ACTIVE_TURNS: dict[str, str] = {}
DELETING_DESIGNS: set[str] = set()
STATE_LOCK = threading.RLock()
JOBS = JobManager()

app = FastAPI(title="Flowline", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    try:
        provider = create_provider()
        return {
            "ready": True,
            "provider": provider.name,
            "model": provider.model,
            "profiles": available_profiles(),
        }
    except ConfigError as exc:
        return JSONResponse(
            status_code=503,
            content={"ready": False, "error": str(exc), "profiles": available_profiles()},
        )


@app.get("/api/profiles")
def profiles() -> dict:
    return {
        "profiles": [
            {
                "id": profile_id,
                "name": load_profile(profile_id).name,
                "region": load_profile(profile_id).region,
                "status": load_profile(profile_id).status,
                "disclaimer": load_profile(profile_id).disclaimer,
                "sources": load_profile(profile_id).sources,
            }
            for profile_id in available_profiles()
        ]
    }


@app.get("/api/projects")
def list_projects() -> dict:
    projects = storage.list_projects()
    return {
        "projects": [
            {
                "project_id": project.id,
                "name": project.name,
                "units": project.building.units,
                "designs": len(project.designs),
                "rooms": len(project.building.rooms),
                "updated_at": project.updated_at,
            }
            for project in projects
        ]
    }


@app.post("/api/projects")
async def upload_project(file: UploadFile = File(...)) -> dict:  # noqa: B008
    filename = Path(file.filename or "plan.dxf").name
    if Path(filename).suffix.lower() != ".dxf":
        raise HTTPException(status_code=400, detail="Only .dxf files are supported.")
    payload = await file.read()
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="DXF must be smaller than 20 MB.")
    project_id = uuid.uuid4().hex[:10]
    target = storage.workspace_dir(project_id) / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    try:
        building = import_dxf(target)
    except DxfImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    project = Project(id=project_id, name=filename, source_path=target, building=building)
    storage.save_project(project)
    with STATE_LOCK:
        PROJECTS[project_id] = project
    return _project_payload(project)


@app.post("/api/projects/sample")
def sample_project(name: str = Query("apartment")) -> dict:
    if name not in {"apartment", "tight_bathroom"}:
        raise HTTPException(status_code=404, detail="Unknown sample.")
    source = SAMPLES_DIR / f"{name}.dxf"
    if not source.exists():
        raise HTTPException(status_code=404, detail="Sample not generated.")
    project_id = uuid.uuid4().hex[:10]
    target = storage.workspace_dir(project_id) / source.name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    building = import_dxf(target)
    project = Project(id=project_id, name=source.name, source_path=target, building=building)
    storage.save_project(project)
    with STATE_LOCK:
        PROJECTS[project_id] = project
    return _project_payload(project)


@app.get("/api/projects/{project_id}")
def get_project(project_id: str) -> dict:
    return _project_payload(_project(project_id))


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str) -> Response:
    project = _project(project_id)
    deleting = set(project.designs)
    if not _cancel_turns_for_deletion(deleting):
        _release_deleting(deleting)
        raise HTTPException(
            status_code=409,
            detail="The assistant is still finishing a design in this drawing. Try deleting again in a moment.",
        )

    try:
        with STATE_LOCK:
            if not storage.delete_project(project_id):
                raise HTTPException(status_code=404, detail="Unknown project.")
            for design_id in deleting:
                DESIGNS.pop(design_id, None)
            PROJECTS.pop(project_id, None)
    finally:
        _release_deleting(deleting)
    return Response(status_code=204)


@app.get("/api/projects/{project_id}/svg")
def project_svg(project_id: str) -> Response:
    project = _project(project_id)
    return Response(render_svg(project.building), media_type="image/svg+xml")


@app.get("/api/projects/{project_id}/designs")
def project_designs(project_id: str) -> dict:
    project = _project(project_id)
    return {
        "designs": [
            _design_summary(project, design_id) for design_id in project.designs
        ]
    }


@app.post("/api/projects/{project_id}/designs")
def create_design(project_id: str, request: DesignRequest) -> dict:
    project = _project(project_id)
    try:
        provider = _provider(request.provider)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session = _new_design(project, request, provider)
    payload = _design_payload(session)
    payload["messages"] = []
    payload["events"] = []
    return payload


@app.post("/api/projects/{project_id}/design")
def start_design(project_id: str, request: DesignRequest) -> dict:
    """Compatibility path: create a design and run its first turn immediately."""
    project = _project(project_id)
    try:
        provider = _provider(request.provider)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session = _new_design(project, request, provider)
    room_text = "; ".join(
        f"{project.building.room(choice.room_id).name or choice.room_id} with "
        + ", ".join(item.value for item in choice.fixture_types)
        for choice in session.room_choices
    )
    content = request.request or (
        f"Design the plumbing for {room_text}. "
        "Use plan_room_layouts so every selected room stays in one design."
    )
    job = _start_turn(project, session, provider, content)
    return {
        "job_id": job.id,
        "design_id": session.design_id,
        "provider": provider.name,
        "model": provider.model,
    }


@app.get("/api/designs/{design_id}")
def get_design(design_id: str) -> dict:
    session = _design(design_id)
    payload = _design_payload(session)
    payload["messages"] = storage.load_messages(session.project_id, design_id)
    payload["events"] = storage.load_events(session.project_id, design_id)
    return payload


@app.delete("/api/designs/{design_id}")
def delete_design(design_id: str) -> Response:
    project_id = storage.project_for_design(design_id)
    if not project_id:
        raise HTTPException(status_code=404, detail="Unknown design.")
    project = _project(project_id)
    if design_id not in project.designs:
        raise HTTPException(status_code=404, detail="Unknown design.")
    with STATE_LOCK:
        if design_id in DELETING_DESIGNS:
            raise HTTPException(
                status_code=409,
                detail="This design is already being deleted.",
            )

    deleting = {design_id}
    if not _cancel_turns_for_deletion(deleting):
        _release_deleting(deleting)
        raise HTTPException(
            status_code=409,
            detail="The assistant is still finishing this run. Try deleting again in a moment.",
        )

    try:
        with STATE_LOCK:
            if not storage.delete_design(project.id, design_id):
                raise HTTPException(status_code=404, detail="Unknown design.")
            DESIGNS.pop(design_id, None)
            PROJECTS.pop(project.id, None)
    finally:
        _release_deleting(deleting)
    return Response(status_code=204)


@app.get("/api/designs/{design_id}/messages")
def get_design_messages(design_id: str) -> dict:
    session = _design(design_id)
    return {"messages": storage.load_messages(session.project_id, design_id)}


@app.get("/api/designs/{design_id}/events")
def get_design_events(design_id: str, after_seq: int = 0) -> dict:
    session = _design(design_id)
    return {
        "events": storage.load_events(
            session.project_id, design_id, after_seq=after_seq
        )
    }


@app.post("/api/designs/{design_id}/messages")
def send_message(design_id: str, request: MessageRequest) -> dict:
    content = request.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    session = _design(design_id)
    project = _project(session.project_id)
    try:
        provider = _provider(None)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    job = _start_turn(project, session, provider, content)
    return {
        "job_id": job.id,
        "design_id": design_id,
        "provider": provider.name,
        "model": provider.model,
    }


@app.get("/api/designs/{design_id}/preview.svg")
def design_svg(design_id: str) -> Response:
    session = _design(design_id)
    return Response(
        render_svg(session.building, session.design), media_type="image/svg+xml"
    )


@app.get("/api/designs/{design_id}/sheet.svg")
def sheet_svg(design_id: str, page: int = Query(1, ge=1)) -> FileResponse:
    session = _design(design_id)
    if not session.sheet_ready or not session.sheet_path:
        try:
            TOOLS["prepare_sheet"].run({}, session)
        except ToolError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        storage.save_design(session)
    if page > session.sheet_pages:
        raise HTTPException(status_code=404, detail="Unknown sheet page.")
    path = session.out_dir / f"sheet-{page}.svg"
    if not path.exists() and session.sheet_svg_path and page == 1:
        path = Path(session.sheet_svg_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Sheet preview has not been generated.")
    return FileResponse(path, media_type="image/svg+xml", filename=f"P-101-{page}.svg")


@app.get("/api/designs/{design_id}/sheet.pdf")
def sheet_pdf(design_id: str) -> FileResponse:
    session = _design(design_id)
    if not session.sheet_ready or not session.sheet_pdf_path:
        try:
            TOOLS["prepare_sheet"].run({}, session)
        except ToolError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        storage.save_design(session)
    if not session.sheet_pdf_path or not Path(session.sheet_pdf_path).exists():
        raise HTTPException(status_code=404, detail="Sheet PDF has not been generated.")
    return FileResponse(
        session.sheet_pdf_path,
        media_type="application/pdf",
        filename=f"{design_id}-sheet.pdf",
    )


@app.patch("/api/designs/{design_id}/sheet")
def update_sheet(design_id: str, request: SheetRequest) -> dict:
    session = _design(design_id)
    args = {key: value for key, value in request.model_dump().items() if value is not None}
    try:
        TOOLS["set_sheet_options"].run(args, session)
        TOOLS["prepare_sheet"].run({}, session)
    except ToolError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    storage.save_design(session)
    return _design_payload(session)


@app.patch("/api/designs/{design_id}")
def update_design(design_id: str, request: ProfileRequest) -> dict:
    session = _design(design_id)
    try:
        load_profile(request.profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if request.profile_id != session.profile_id:
        previous = session.profile_id
        session.profile_id = request.profile_id
        if session.design is not None:
            session.design.profile_id = request.profile_id
        session.stale = True
        session.add_decision(
            "profile_changed",
            previous_profile=previous,
            profile_id=request.profile_id,
            reason="Standard changed from the design header.",
        )
        storage.save_design(session)
    return _design_payload(session)


@app.post("/api/designs/{design_id}/fix")
def fix_design(design_id: str, request: FixRequest) -> dict:
    session = _design(design_id)
    if session.design is None:
        raise HTTPException(
            status_code=409,
            detail="There is no completed design to work with yet. Generate a design first.",
        )
    fix = next((item for item in session.fixes if item.id == request.fix_id), None)
    if fix is None:
        raise HTTPException(status_code=404, detail="Unknown fix.")
    try:
        updated = apply_fix(
            session.building,
            session.design,
            fix,
            session.profile(),
            session.candidates,
            session.candidates_by_room,
        )
    except FixError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.design = updated
    session.applied_fixes.append(fix.id)
    try:
        build_plumbing(session.building, updated, session.profile())
    except RouteError:
        pass
    session.validation = validate_design(session.building, updated, session.profile())
    session.fixes = recommend_fixes(
        session.building,
        updated,
        session.validation,
        session.profile(),
        session.candidates,
        session.candidates_by_room,
    )
    session.sheet_ready = False
    session.drawing_review = []
    session.sheet_path = None
    session.sheet_svg_path = None
    session.sheet_pdf_path = None
    session.sheet_pages = 0
    explained = TOOLS["explain_design"].run({}, session)
    session.final_answer = explained["explanation"]
    session.add_decision(
        "fix_applied",
        fix_id=fix.id,
        kind=fix.kind,
        description=fix.description,
        after=summarize(session.validation),
    )
    storage.save_design(session)
    return _design_payload(session)


@app.post("/api/designs/{design_id}/approve")
def approve_design(design_id: str, request: ApproveRequest) -> dict:
    session = _design(design_id)
    if session.design is None:
        raise HTTPException(
            status_code=409,
            detail="There is no completed design to work with yet. Generate a design first.",
        )
    counts = summarize(session.validation)
    session.approved = True
    try:
        exported = TOOLS["export_dxf"].run({}, session)
    except ToolError as exc:
        session.approved = False
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    profile = session.profile()
    report_stacks = list(session.stacks.values()) or (
        [session.stack] if session.stack is not None else []
    )
    report = {
        "design_id": design_id,
        "approver": request.approver_name,
        "approved_at": time.time(),
        "provider": session.provider_name,
        "model": session.model_name,
        "profile": profile.id,
        "profile_name": profile.name,
        "disclaimer": profile.disclaimer,
        "counts": counts,
        "room_ids": session.design.room_ids,
        "stacks": [stack.model_dump(mode="json") for stack in report_stacks],
        "design": session.design.model_dump(mode="json"),
        "validation": [item.model_dump(mode="json") for item in session.validation],
        "drawing_review": [
            item.model_dump(mode="json") for item in session.drawing_review
        ],
        "sheet_pages": session.sheet_pages,
        "applied_fixes": session.applied_fixes,
        "exported_path": exported["path"],
    }
    (session.out_dir / "approval.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    ActionLogger(session.out_dir / "audit.jsonl").log_event(
        request_id=design_id,
        kind="approval",
        payload={"approver": request.approver_name, "exported_path": exported["path"]},
        provider=session.provider_name,
        model=session.model_name,
    )
    storage.save_design(session)
    payload = _design_payload(session)
    payload["download_url"] = f"/api/designs/{design_id}/download.dxf"
    payload["approval_report"] = str(session.out_dir / "approval.json")
    return payload


@app.get("/api/designs/{design_id}/download.dxf")
def download_dxf(design_id: str) -> FileResponse:
    session = _design(design_id)
    if not session.exported_path or not Path(session.exported_path).exists():
        raise HTTPException(status_code=404, detail="Design has not been approved/exported.")
    return FileResponse(
        session.exported_path,
        media_type="application/dxf",
        filename=f"{design_id}.dxf",
    )


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job.")
    return {
        "job_id": job.id,
        "status": job.status,
        "done": job.done,
        "error": job.error,
        "result": job.result,
    }


@app.get("/api/jobs/{job_id}/events")
def job_events(job_id: str) -> StreamingResponse:
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job.")
    return StreamingResponse(
        JOBS.stream(job),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _project(project_id: str) -> Project:
    with STATE_LOCK:
        project = PROJECTS.get(project_id)
    if project is not None:
        return project
    project = storage.load_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Unknown project.")
    with STATE_LOCK:
        PROJECTS[project_id] = project
    return project


def _cancel_turns_for_deletion(
    design_ids: set[str], timeout: float = 30.0
) -> bool:
    with STATE_LOCK:
        for design_id in design_ids:
            job_id = ACTIVE_TURNS.get(design_id)
            if job_id:
                JOBS.cancel(job_id)
            DELETING_DESIGNS.add(design_id)

    deadline = time.monotonic() + timeout
    while True:
        with STATE_LOCK:
            if not design_ids.intersection(ACTIVE_TURNS):
                return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)


def _release_deleting(design_ids: set[str]) -> None:
    with STATE_LOCK:
        DELETING_DESIGNS.difference_update(design_ids)


def _design(design_id: str) -> AgentSession:
    with STATE_LOCK:
        session = DESIGNS.get(design_id)
    if session is not None:
        return session
    project_id = storage.project_for_design(design_id)
    if not project_id:
        raise HTTPException(status_code=404, detail="Unknown design.")
    project = _project(project_id)
    session = storage.load_design(project, design_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Unknown design.")
    if session.design is not None and session.validation:
        session.fixes = recommend_fixes(
            session.building,
            session.design,
            session.validation,
            session.profile(),
            session.candidates,
            session.candidates_by_room,
        )
        storage.save_design(session)
    with STATE_LOCK:
        DESIGNS[design_id] = session
    return session


def _provider(requested: str | None):
    env = dict(os.environ)
    if requested:
        env["LLM_PROVIDER"] = requested
    return create_provider(env)


def _resolve_room_choices(
    building: Building, request: DesignRequest
) -> tuple[list[RoomChoice], dict[str, Stack]]:
    if request.rooms:
        selections = list(request.rooms)
    elif request.room_id:
        selections = [
            RoomSelection(room_id=request.room_id, fixtures=request.fixtures)
        ]
    else:
        raise HTTPException(
            status_code=400,
            detail="Select at least one plumbing room.",
        )

    if request.stack is not None:
        stacks = stacks_for_building(building, manual_stack=request.stack)
    elif request.shaft_id and not request.rooms:
        stacks = stacks_for_building(building, shaft_id=request.shaft_id)
    else:
        stacks = stacks_for_building(building)
    if not stacks:
        raise HTTPException(
            status_code=400,
            detail="No shaft found. Provide a stack point or draw a shaft.",
        )
    stack_map = {stack.id: stack for stack in stacks}

    choices: list[RoomChoice] = []
    seen: set[str] = set()
    for selection in selections:
        if selection.room_id in seen:
            raise HTTPException(
                status_code=400,
                detail=f"Room {selection.room_id} was selected more than once.",
            )
        seen.add(selection.room_id)
        try:
            room = building.room(selection.room_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        fixture_types = (
            list(selection.fixtures)
            if selection.fixtures is not None
            else list(room.default_fixtures)
        )
        if not fixture_types:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Room {room.name or room.id} has no plumbing fixtures selected."
                ),
            )
        stack = (
            stack_map.get(selection.stack_id)
            if selection.stack_id
            else nearest_stack(room, stacks)
        )
        if stack is None:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown stack {selection.stack_id!r}.",
            )
        choices.append(
            RoomChoice(
                room_id=room.id,
                fixture_types=fixture_types,
                stack_id=stack.id,
            )
        )
    return choices, stack_map


def _new_design(project: Project, request: DesignRequest, provider) -> AgentSession:
    choices, stacks = _resolve_room_choices(project.building, request)
    try:
        load_profile(request.profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    primary = choices[0]
    primary_stack = stacks[primary.stack_id]
    design_id = f"DES-{uuid.uuid4().hex[:8]}"
    out_dir = storage.design_dir(project.id, design_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    session = AgentSession(
        building=project.building,
        source_path=project.source_path,
        out_dir=out_dir,
        room_id=primary.room_id,
        fixture_types=list(primary.fixture_types),
        stack=primary_stack,
        stacks=stacks,
        room_choices=choices,
        profile_id=request.profile_id,
        design_id=design_id,
        project_id=project.id,
        provider_name=provider.name,
        model_name=provider.model,
    )
    storage.save_design(session)
    storage.register_design(project.id, design_id)
    if design_id not in project.designs:
        project.designs.append(design_id)
        project.updated_at = time.time()
        storage.save_project(project)
    with STATE_LOCK:
        DESIGNS[design_id] = session
    return session


def _start_turn(
    project: Project,
    session: AgentSession,
    provider,
    content: str,
) -> Job:
    design_id = session.design_id
    with STATE_LOCK:
        if design_id in DELETING_DESIGNS:
            raise HTTPException(
                status_code=409,
                detail="This design is being deleted. Choose another design.",
            )
        if design_id in ACTIVE_TURNS:
            raise HTTPException(
                status_code=409,
                detail="The assistant is already working on this design. Wait for the current run to finish, then try again.",
            )
        job = JOBS.create(project_id=project.id, design_id=design_id)
        ACTIVE_TURNS[design_id] = job.id
    prior = storage.load_messages(project.id, design_id)
    history = [
        ChatMessage(role=item["role"], content=item["content"])
        for item in prior
        if item.get("role") in ("user", "assistant") and item.get("content")
    ]
    storage.append_message(
        project.id, design_id, "user", content, turn_id=job.id
    )
    session.provider_name = provider.name
    session.model_name = provider.model

    def work(current: Job) -> None:
        def emit(event: dict) -> None:
            persisted = storage.append_event(
                project.id, design_id, event, turn_id=current.id
            )
            current.emit(persisted)
            if event.get("type") in (
                "turn_start",
                "plan",
                "decision",
                "reasoning",
                "tool_result",
                "final",
                "snapshot",
            ):
                try:
                    storage.save_design(session)
                except Exception:
                    pass

        try:
            runner = AgentRunner(
                provider,
                max_iterations=int(os.getenv("AGENT_MAX_ITERATIONS", "12")),
                logger=ActionLogger(session.out_dir / "audit.jsonl"),
                on_event=emit,
            )
            result = runner.run_turn(
                content,
                session,
                history=history,
                request_id=current.id,
                should_cancel=current.cancel_requested.is_set,
            )
            session.final_answer = result.final_answer
            if session.design is not None:
                session.design.id = design_id
            storage.append_message(
                project.id,
                design_id,
                "assistant",
                result.final_answer,
                turn_id=current.id,
            )
            storage.save_design(session)
            payload = _design_payload(
                session,
                final_answer=result.final_answer,
                stopped_reason=result.stopped_reason,
            )
            current.result = payload
            current.status = "done" if result.stopped_reason == "final" else "error"
            if current.status == "error":
                current.error = result.final_answer
            emit({"type": "snapshot", **payload})
        finally:
            with STATE_LOCK:
                ACTIVE_TURNS.pop(design_id, None)

    JOBS.start(job, work)
    return job





def _project_payload(project: Project) -> dict:
    building = project.building
    stacks = stacks_for_building(building)
    water_sources = water_sources_for_building(building)
    return {
        "project_id": project.id,
        "name": project.name,
        "units": building.units,
        "source_scale": building.source_scale,
        "warnings": building.warnings,
        "rooms": [
            {
                "id": room.id,
                "name": room.name,
                "area_m2": round(room.area_m2, 3),
                "width_mm": round(room.bbox.width, 1),
                "height_mm": round(room.bbox.height, 1),
                "wet_area": room.is_wet_area,
                "plumbing_role": room.plumbing_role.value,
                "default_fixtures": [
                    fixture.value for fixture in room.default_fixtures
                ],
                "fixture_hints": [
                    fixture.value for fixture in room.fixture_hints
                ],
                "fixtures": [
                    _detected_fixture_payload(fixture)
                    for fixture in building.detected_fixtures
                    if fixture.room_id == room.id
                ],
                "default_stack_id": (
                    nearest_stack(room, stacks).id
                    if nearest_stack(room, stacks) is not None
                    else None
                ),
                "closed": room.is_closed,
            }
            for room in building.rooms
        ],
        "detected_fixtures": [
            _detected_fixture_payload(fixture)
            for fixture in building.detected_fixtures
        ],
        "stacks": [
            {
                "id": stack.id,
                "x": stack.position.x,
                "y": stack.position.y,
                "diameter_mm": stack.diameter_mm,
                "shaft_id": stack.shaft_id,
            }
            for stack in stacks
        ],
        "water_sources": [
            {
                "id": source.id,
                "x": source.position.x,
                "y": source.position.y,
                "shaft_id": source.shaft_id,
            }
            for source in water_sources
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
        "designs": [
            _design_summary(project, design_id) for design_id in project.designs
        ],
        "svg": render_svg(building),
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


def _detected_fixture_payload(fixture) -> dict:
    return {
        "id": fixture.id,
        "type": fixture.type.value,
        "room_id": fixture.room_id,
        "x": fixture.position.x,
        "y": fixture.position.y,
        "width_mm": fixture.width_mm,
        "depth_mm": fixture.depth_mm,
        "block_name": fixture.block_name,
        "layer": fixture.layer,
        "source": fixture.source,
        "confidence": fixture.confidence,
    }


def _design_summary(project: Project, design_id: str) -> dict:
    session = storage.load_design(project, design_id)
    if session is None:
        return {"design_id": design_id, "status": "missing"}
    counts = summarize(session.validation) if session.validation else {
        "PASS": 0,
        "WARNING": 0,
        "ERROR": 0,
    }
    if session.approved:
        status = "approved"
    elif session.stale:
        status = "stale"
    elif session.design is not None and session.validation:
        status = "validated" if counts["ERROR"] == 0 else "needs_fix"
    elif session.design is not None:
        status = "drafted"
    else:
        status = "setup"
    room_ids = (
        session.design.room_ids
        if session.design is not None
        else [choice.room_id for choice in session.room_choices]
    )
    return {
        "design_id": design_id,
        "room_id": session.room_id,
        "room_ids": room_ids,
        "profile_id": session.profile_id,
        "layout_id": session.design.layout_id if session.design else None,
        "status": status,
        "counts": counts,
        "approved": session.approved,
    }


def _design_payload(
    session: AgentSession,
    *,
    final_answer: str | None = None,
    stopped_reason: str | None = None,
) -> dict:
    design = session.design
    profile = session.profile()
    counts = summarize(session.validation) if session.validation else {
        "PASS": 0,
        "WARNING": 0,
        "ERROR": 0,
    }
    issues = [
        result.model_dump(mode="json")
        for result in session.validation
        if result.severity != Severity.PASS
    ]
    selected_id = design.layout_id if design else None
    room_ids = design.room_ids if design else [
        choice.room_id for choice in session.room_choices
    ]
    room_plans = (
        [plan.model_dump(mode="json") for plan in design.room_plans]
        if design
        else [
            {
                "room_id": choice.room_id,
                "fixture_types": [item.value for item in choice.fixture_types],
                "layout_id": None,
                "stack_id": choice.stack_id,
                "rationale": None,
            }
            for choice in session.room_choices
        ]
    )
    stacks = list(session.stacks.values())
    if not stacks and session.stack is not None:
        stacks = [session.stack]
    return {
        "design_id": session.design_id or (design.id if design else None),
        "project_id": session.project_id,
        "room_id": session.room_id,
        "room_ids": room_ids,
        "room_plans": room_plans,
        "fixtures_by_room": [
            {
                "room_id": choice.room_id,
                "fixtures": [item.value for item in choice.fixture_types],
            }
            for choice in session.room_choices
        ],
        "stacks": [stack.model_dump(mode="json") for stack in stacks],
        "water_sources": (
            [source.model_dump(mode="json") for source in design.water_sources]
            if design
            else []
        ),
        "vent_stacks": (
            [stack.model_dump(mode="json") for stack in design.vent_stacks]
            if design
            else []
        ),
        "fixtures": [fixture.value for fixture in session.fixture_types],
        "stack": session.stack.model_dump(mode="json") if session.stack else None,
        "profile_id": profile.id,
        "profile_name": profile.name,
        "disclaimer": profile.disclaimer,
        "provider": session.provider_name,
        "model": session.model_name,
        "stopped_reason": stopped_reason,
        "final_answer": final_answer if final_answer is not None else session.final_answer,
        "counts": counts,
        "issues": issues,
        "fixes": [
            {"id": fix.id, "kind": fix.kind, "description": fix.description}
            for fix in session.fixes
        ],
        "candidates": [
            {
                "id": candidate.id,
                "pattern": candidate.pattern,
                "score": round(candidate.score, 1),
                "violations": candidate.violations,
                "rationale_hint": candidate.rationale_hint,
                "selected": candidate.id == selected_id,
            }
            for candidate in session.candidates
        ],
        "design": design.model_dump(mode="json") if design else None,
        "vent_pipes": (
            [pipe.model_dump(mode="json") for pipe in design.vent_pipes]
            if design
            else []
        ),
        "supply_pipes": (
            [pipe.model_dump(mode="json") for pipe in design.supply_pipes]
            if design
            else []
        ),
        "plumbing_items": (
            [item.model_dump(mode="json") for item in design.plumbing_items]
            if design
            else []
        ),
        "vent_stack": (
            design.vent_stack.model_dump(mode="json")
            if design and design.vent_stack
            else None
        ),
        "water_source": (
            design.water_source.model_dump(mode="json")
            if design and design.water_source
            else None
        ),
        "sheet": design.sheet.model_dump(mode="json") if design else None,
        "drawing_review": [
            item.model_dump(mode="json") for item in session.drawing_review
        ],
        "sheet_ready": session.sheet_ready,
        "sheet_pages": session.sheet_pages,
        "sheet_svg_url": f"/api/designs/{session.design_id}/sheet.svg"
        if session.sheet_ready
        else None,
        "sheet_pdf_url": f"/api/designs/{session.design_id}/sheet.pdf"
        if session.sheet_ready
        else None,
        "validation": [result.model_dump(mode="json") for result in session.validation],
        "decisions": session.decisions,
        "plan": session.plan,
        "stale": session.stale,
        "applied_fixes": session.applied_fixes,
        "exported_path": session.exported_path,
        "approved": session.approved,
        "svg": render_svg(session.building, design) if design else render_svg(session.building),
        "download_url": (
            f"/api/designs/{session.design_id}/download.dxf"
            if session.exported_path
            else None
        ),
    }
