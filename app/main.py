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
from agent.tools import TOOLS, AgentSession, ToolError
from app import storage
from app.jobs import Job, JobManager
from app.models import Project
from app.schemas import (
    ApproveRequest,
    DesignRequest,
    FixRequest,
    MessageRequest,
    ProfileRequest,
)
from core.dxf_import import DxfImportError, import_dxf
from core.fixes import FixError, apply_fix, recommend_fixes
from core.models import Building, Severity, Stack
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
    content = request.request or (
        f"Design the drainage for room {session.room_id} with "
        f"{', '.join(item.value for item in session.fixture_types)} and explain the result."
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
        raise HTTPException(status_code=409, detail="No design selected.")
    fix = next((item for item in session.fixes if item.id == request.fix_id), None)
    if fix is None:
        raise HTTPException(status_code=404, detail="Unknown fix.")
    try:
        updated = apply_fix(
            session.building, session.design, fix, session.profile(), session.candidates
        )
    except FixError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.design = updated
    session.applied_fixes.append(fix.id)
    session.validation = validate_design(session.building, updated, session.profile())
    session.fixes = recommend_fixes(
        session.building, updated, session.validation, session.profile(), session.candidates
    )
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
        raise HTTPException(status_code=409, detail="No design selected.")
    if session.stale:
        raise HTTPException(
            status_code=409,
            detail="The standard changed. Revalidate before approving.",
        )
    counts = summarize(session.validation)
    if counts["ERROR"]:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Fix all ERRORs before export.",
                "counts": counts,
                "issues": [
                    result.model_dump(mode="json")
                    for result in session.validation
                    if result.severity == Severity.ERROR
                ],
            },
        )
    session.approved = True
    try:
        exported = TOOLS["export_dxf"].run({}, session)
    except ToolError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    profile = session.profile()
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
        "design": session.design.model_dump(mode="json"),
        "validation": [item.model_dump(mode="json") for item in session.validation],
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
    with STATE_LOCK:
        DESIGNS[design_id] = session
    return session


def _provider(requested: str | None):
    env = dict(os.environ)
    if requested:
        env["LLM_PROVIDER"] = requested
    return create_provider(env)


def _new_design(project: Project, request: DesignRequest, provider) -> AgentSession:
    try:
        room = project.building.room(request.room_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    stack = _resolve_stack(project.building, request)
    try:
        load_profile(request.profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    design_id = f"DES-{uuid.uuid4().hex[:8]}"
    out_dir = storage.design_dir(project.id, design_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    session = AgentSession(
        building=project.building,
        source_path=project.source_path,
        out_dir=out_dir,
        room_id=room.id,
        fixture_types=request.fixtures,
        stack=stack,
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
        if design_id in ACTIVE_TURNS:
            raise HTTPException(
                status_code=409,
                detail="The agent is already working on this design.",
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
                content, session, history=history, request_id=current.id
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


def _resolve_stack(building: Building, request: DesignRequest) -> Stack:
    if request.stack is not None:
        return Stack(id="S1", position=request.stack)
    if request.shaft_id:
        shaft = next(
            (item for item in building.shafts if item.id == request.shaft_id), None
        )
        if shaft is None:
            raise HTTPException(status_code=404, detail="Unknown shaft.")
        return Stack(id="S1", position=shaft.position)
    if building.shafts:
        return Stack(id="S1", position=building.shafts[0].position)
    raise HTTPException(
        status_code=400,
        detail="No shaft found. Provide a stack point or draw a shaft.",
    )


def _project_payload(project: Project) -> dict:
    building = project.building
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
                "closed": room.is_closed,
            }
            for room in building.rooms
        ],
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
        "designs": [
            _design_summary(project, design_id) for design_id in project.designs
        ],
        "svg": render_svg(building),
        "created_at": project.created_at,
        "updated_at": project.updated_at,
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
    return {
        "design_id": design_id,
        "room_id": session.room_id,
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
    return {
        "design_id": session.design_id or (design.id if design else None),
        "project_id": session.project_id,
        "room_id": session.room_id,
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
