from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

import config  # noqa: F401  (loads .env)
from agent.logging import ActionLogger
from agent.loop import AgentRunner
from agent.providers.base import ConfigError
from agent.providers.factory import create_provider
from agent.tools import TOOLS, AgentSession, ToolError
from app.jobs import Job, JobManager
from app.schemas import ApproveRequest, DesignRequest, FixRequest
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
DATA_DIR = ROOT / "data"
PROJECT_DIR = DATA_DIR / "projects"
DESIGN_DIR = DATA_DIR / "designs"
SAMPLES_DIR = ROOT / "samples"
STATIC_DIR = Path(__file__).resolve().parent / "static"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024

PROJECT_DIR.mkdir(parents=True, exist_ok=True)
DESIGN_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Project:
    id: str
    building: Building
    source_path: Path
    name: str


PROJECTS: dict[str, Project] = {}
DESIGNS: dict[str, AgentSession] = {}
STATE_LOCK = threading.Lock()
JOBS = JobManager()

app = FastAPI(title="Flowline", version="0.1.0")
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


@app.post("/api/projects")
async def upload_project(file: UploadFile = File(...)) -> dict:  # noqa: B008
    filename = Path(file.filename or "plan.dxf").name
    if Path(filename).suffix.lower() != ".dxf":
        raise HTTPException(status_code=400, detail="Only .dxf files are supported.")
    payload = await file.read()
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="DXF must be smaller than 20 MB.")
    project_id = uuid.uuid4().hex[:10]
    target = PROJECT_DIR / project_id / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    try:
        building = import_dxf(target)
    except DxfImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    project = Project(id=project_id, building=building, source_path=target, name=filename)
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
    target = PROJECT_DIR / project_id / source.name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    building = import_dxf(target)
    project = Project(id=project_id, building=building, source_path=target, name=source.name)
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


@app.post("/api/projects/{project_id}/design")
def start_design(project_id: str, request: DesignRequest) -> dict:
    project = _project(project_id)
    try:
        room = project.building.room(request.room_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    stack = _resolve_stack(project.building, request)
    try:
        load_profile(request.profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        provider = _provider(request.provider)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    design_id = f"DES-{uuid.uuid4().hex[:8]}"
    out_dir = DESIGN_DIR / design_id
    out_dir.mkdir(parents=True, exist_ok=True)
    session = AgentSession(
        building=project.building,
        source_path=project.source_path,
        out_dir=out_dir,
        room_id=room.id,
        fixture_types=request.fixtures,
        stack=stack,
        profile_id=request.profile_id,
        provider_name=provider.name,
        model_name=provider.model,
    )
    job = JOBS.create(project_id=project_id, design_id=design_id)
    agent_request = request.request or (
        f"Design the drainage for room {room.id} with "
        f"{', '.join(item.value for item in request.fixtures)} and explain the result."
    )

    def work(current: Job) -> None:
        runner = AgentRunner(
            provider,
            max_iterations=int(os.getenv("AGENT_MAX_ITERATIONS", "12")),
            logger=ActionLogger(out_dir / "audit.jsonl"),
            on_event=current.emit,
        )
        result = runner.run(agent_request, session, request_id=current.id)
        session.final_answer = result.final_answer
        if session.design is not None:
            session.design.id = design_id
            with STATE_LOCK:
                DESIGNS[design_id] = session
        payload = _design_payload(session, final_answer=result.final_answer,
                                  stopped_reason=result.stopped_reason)
        current.result = payload
        current.status = "done" if result.stopped_reason == "final" else "error"
        if current.status == "error":
            current.error = result.final_answer
        current.emit({"type": "snapshot", **payload})

    JOBS.start(job, work)
    return {
        "job_id": job.id,
        "design_id": design_id,
        "provider": provider.name,
        "model": provider.model,
    }


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


@app.get("/api/designs/{design_id}")
def get_design(design_id: str) -> dict:
    session = _design(design_id)
    return _design_payload(session)


@app.get("/api/designs/{design_id}/preview.svg")
def design_svg(design_id: str) -> Response:
    session = _design(design_id)
    return Response(
        render_svg(session.building, session.design), media_type="image/svg+xml"
    )


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
    with STATE_LOCK:
        DESIGNS[design_id] = session
    return _design_payload(session)


@app.post("/api/designs/{design_id}/approve")
def approve_design(design_id: str, request: ApproveRequest) -> dict:
    session = _design(design_id)
    if session.design is None:
        raise HTTPException(status_code=409, detail="No design selected.")
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
    with STATE_LOCK:
        DESIGNS[design_id] = session
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


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _project(project_id: str) -> Project:
    with STATE_LOCK:
        project = PROJECTS.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Unknown project.")
    return project


def _design(design_id: str) -> AgentSession:
    with STATE_LOCK:
        session = DESIGNS.get(design_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Unknown or unfinished design.")
    return session


def _provider(requested: str | None):
    env = dict(os.environ)
    if requested:
        env["LLM_PROVIDER"] = requested
    return create_provider(env)


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
        "svg": render_svg(building),
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
    return {
        "design_id": design.id if design else None,
        "room_id": session.room_id,
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
            }
            for candidate in session.candidates
        ],
        "design": design.model_dump(mode="json") if design else None,
        "validation": [result.model_dump(mode="json") for result in session.validation],
        "applied_fixes": session.applied_fixes,
        "exported_path": session.exported_path,
        "svg": render_svg(session.building, design) if design else render_svg(session.building),
        "download_url": (
            f"/api/designs/{design.id}/download.dxf" if design and session.exported_path else None
        ),
    }
