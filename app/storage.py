from __future__ import annotations

import json
import os
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from agent.tools import AgentSession
from app.models import Project
from core.models import Building, Design, Fix, FixtureType, LayoutCandidate, Stack, ValidationResult
from core.svg import render_svg

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("FLOWLINE_DATA_DIR", ROOT / "data"))
WORKSPACES_DIR = DATA_DIR / "workspaces"
DESIGN_INDEX = DATA_DIR / "design_index.json"
_LOCK = threading.RLock()


def workspace_dir(project_id: str) -> Path:
    return WORKSPACES_DIR / project_id


def design_dir(project_id: str, design_id: str) -> Path:
    return workspace_dir(project_id) / "designs" / design_id


def save_project(project: Project) -> None:
    with _LOCK:
        ws = workspace_dir(project.id)
        ws.mkdir(parents=True, exist_ok=True)
        source = Path(project.source_path)
        target = ws / source.name
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        project.source_path = target
        project.updated_at = time.time()
        data = {
            "id": project.id,
            "name": project.name,
            "source_file": target.name,
            "building": project.building.model_dump(mode="json"),
            "designs": project.designs,
            "created_at": project.created_at,
            "updated_at": project.updated_at,
        }
        _write_json(ws / "workspace.json", data)


def load_project(project_id: str) -> Project | None:
    path = workspace_dir(project_id) / "workspace.json"
    if not path.exists():
        return None
    data = _read_json(path)
    source = workspace_dir(project_id) / data.get("source_file", "source.dxf")
    return Project(
        id=str(data["id"]),
        name=str(data.get("name") or project_id),
        source_path=source,
        building=Building.model_validate(data["building"]),
        designs=list(data.get("designs") or []),
        created_at=float(data.get("created_at") or time.time()),
        updated_at=float(data.get("updated_at") or time.time()),
    )


def list_projects() -> list[Project]:
    if not WORKSPACES_DIR.exists():
        return []
    projects = []
    for path in WORKSPACES_DIR.glob("*/workspace.json"):
        try:
            project = load_project(path.parent.name)
        except Exception:
            continue
        if project is not None:
            projects.append(project)
    return sorted(projects, key=lambda item: item.updated_at, reverse=True)


def save_design(session: AgentSession) -> None:
    if not session.project_id or not session.design_id:
        raise ValueError("Design session must have project_id and design_id.")
    with _LOCK:
        target = design_dir(session.project_id, session.design_id)
        target.mkdir(parents=True, exist_ok=True)
        existing = {}
        path = target / "design.json"
        if path.exists():
            try:
                existing = _read_json(path)
            except Exception:
                existing = {}
        data = session_to_dict(session)
        data["created_at"] = existing.get("created_at") or time.time()
        data["updated_at"] = time.time()
        _write_json(path, data)
        (target / "preview.svg").write_text(
            render_svg(session.building, session.design), encoding="utf-8"
        )


def load_design(
    project: Project, design_id: str
) -> AgentSession | None:
    target = design_dir(project.id, design_id) / "design.json"
    if not target.exists():
        return None
    data = _read_json(target)
    return session_from_dict(
        data,
        building=project.building,
        source_path=project.source_path,
        out_dir=design_dir(project.id, design_id),
    )


def register_design(project_id: str, design_id: str) -> None:
    with _LOCK:
        index = {}
        if DESIGN_INDEX.exists():
            try:
                index = _read_json(DESIGN_INDEX)
            except Exception:
                index = {}
        index[design_id] = project_id
        _write_json(DESIGN_INDEX, index)


def project_for_design(design_id: str) -> str | None:
    with _LOCK:
        if DESIGN_INDEX.exists():
            try:
                index = _read_json(DESIGN_INDEX)
                if design_id in index:
                    return str(index[design_id])
            except Exception:
                pass
    if not WORKSPACES_DIR.exists():
        return None
    for path in WORKSPACES_DIR.glob("*/designs/*/design.json"):
        if path.parent.name == design_id:
            return path.parents[2].name
    return None


def append_message(
    project_id: str,
    design_id: str,
    role: str,
    content: str,
    turn_id: str | None = None,
) -> dict:
    with _LOCK:
        target = design_dir(project_id, design_id)
        target.mkdir(parents=True, exist_ok=True)
        path = target / "messages.json"
        messages = _read_json(path) if path.exists() else []
        message = {
            "id": uuid.uuid4().hex[:10],
            "role": role,
            "content": content,
            "turn_id": turn_id,
            "created_at": time.time(),
        }
        messages.append(message)
        _write_json(path, messages)
        return message


def load_messages(project_id: str, design_id: str) -> list[dict]:
    path = design_dir(project_id, design_id) / "messages.json"
    if not path.exists():
        return []
    try:
        data = _read_json(path)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def append_event(
    project_id: str,
    design_id: str,
    event: dict[str, Any],
    turn_id: str | None = None,
) -> dict:
    with _LOCK:
        target = design_dir(project_id, design_id)
        target.mkdir(parents=True, exist_ok=True)
        path = target / "events.jsonl"
        seq = 1
        if path.exists():
            lines = path.read_text(encoding="utf-8").splitlines()
            if lines:
                try:
                    seq = int(json.loads(lines[-1]).get("seq", 0)) + 1
                except Exception:
                    seq = len(lines) + 1
        item = {
            "seq": seq,
            "turn_id": turn_id,
            "at": time.time(),
            **event,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(item, default=str) + "\n")
        return item


def load_events(project_id: str, design_id: str, after_seq: int = 0) -> list[dict]:
    path = design_dir(project_id, design_id) / "events.jsonl"
    if not path.exists():
        return []
    events = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if int(item.get("seq", 0)) > after_seq:
                events.append(item)
    return events


def session_to_dict(session: AgentSession) -> dict:
    return {
        "design_id": session.design_id,
        "project_id": session.project_id,
        "room_id": session.room_id,
        "fixture_types": [fixture.value for fixture in session.fixture_types],
        "stack": session.stack.model_dump(mode="json") if session.stack else None,
        "profile_id": session.profile_id,
        "design": session.design.model_dump(mode="json") if session.design else None,
        "candidates": [
            candidate.model_dump(mode="json") for candidate in session.candidates
        ],
        "validation": [
            result.model_dump(mode="json") for result in session.validation
        ],
        "fixes": [fix.model_dump(mode="json") for fix in session.fixes],
        "decisions": session.decisions,
        "plan": session.plan,
        "stale": session.stale,
        "approved": session.approved,
        "exported_path": session.exported_path,
        "provider_name": session.provider_name,
        "model_name": session.model_name,
        "final_answer": session.final_answer,
        "applied_fixes": session.applied_fixes,
    }


def session_from_dict(
    data: dict,
    *,
    building: Building,
    source_path: Path,
    out_dir: Path,
) -> AgentSession:
    session = AgentSession(
        building=building,
        source_path=source_path,
        out_dir=out_dir,
        room_id=data.get("room_id"),
        fixture_types=[FixtureType(item) for item in data.get("fixture_types") or []]
        or [FixtureType.WC, FixtureType.BASIN, FixtureType.SHOWER],
        stack=Stack.model_validate(data["stack"]) if data.get("stack") else None,
        profile_id=str(data.get("profile_id") or "india_nbc_2016"),
        design_id=str(data.get("design_id") or out_dir.name),
        project_id=str(data.get("project_id") or ""),
        provider_name=str(data.get("provider_name") or ""),
        model_name=str(data.get("model_name") or ""),
        final_answer=str(data.get("final_answer") or ""),
        approved=bool(data.get("approved")),
        exported_path=data.get("exported_path"),
        applied_fixes=list(data.get("applied_fixes") or []),
        decisions=list(data.get("decisions") or []),
        plan=list(data.get("plan") or []),
        stale=bool(data.get("stale")),
    )
    session.design = (
        Design.model_validate(data["design"]) if data.get("design") else None
    )
    session.candidates = [
        LayoutCandidate.model_validate(item) for item in data.get("candidates") or []
    ]
    session.validation = [
        ValidationResult.model_validate(item) for item in data.get("validation") or []
    ]
    session.fixes = [Fix.model_validate(item) for item in data.get("fixes") or []]
    return session


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))
