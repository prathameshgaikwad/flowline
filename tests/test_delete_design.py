import json
import threading
import time

from fastapi.testclient import TestClient

from app import main as main_module
from app import storage
from app.main import app
from app.models import Project
from core.models import Building

client = TestClient(app)


def _sample():
    response = client.post("/api/projects/sample", params={"name": "apartment"})
    assert response.status_code == 200, response.text
    return response.json()


def _create_design(project: dict) -> str:
    bathroom = next(room for room in project["rooms"] if room["wet_area"])
    created = client.post(
        f"/api/projects/{project['project_id']}/designs",
        json={
            "room_id": bathroom["id"],
            "fixtures": ["WC", "BASIN", "SHOWER"],
            "shaft_id": project["shafts"][0]["id"],
            "profile_id": "india_nbc_2016",
        },
    )
    assert created.status_code == 200, created.text
    return created.json()["design_id"]


def test_delete_design_removes_files_project_reference_and_index(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "WORKSPACES_DIR", tmp_path / "workspaces")
    monkeypatch.setattr(storage, "DESIGN_INDEX", tmp_path / "design_index.json")

    source = tmp_path / "plan.dxf"
    source.write_text("source", encoding="utf-8")
    project = Project(
        id="project-delete",
        name="plan.dxf",
        source_path=source,
        building=Building(id="project-delete"),
        designs=["DES-deadbeef"],
    )
    storage.save_project(project)
    storage.register_design("project-delete", "DES-deadbeef")
    design_dir = storage.design_dir("project-delete", "DES-deadbeef")
    design_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "design.json",
        "messages.json",
        "events.jsonl",
        "audit.jsonl",
        "preview.svg",
        "export.dxf",
        "sheet.pdf",
    ):
        (design_dir / name).write_text("{}", encoding="utf-8")

    assert storage.delete_design("project-delete", "DES-deadbeef") is True

    assert not design_dir.exists()
    workspace = json.loads(
        (storage.workspace_dir("project-delete") / "workspace.json").read_text(
            encoding="utf-8"
        )
    )
    assert workspace["designs"] == []
    index = json.loads(storage.DESIGN_INDEX.read_text(encoding="utf-8"))
    assert "DES-deadbeef" not in index
    assert storage.delete_design("project-delete", "DES-deadbeef") is False


def test_delete_project_removes_workspace_and_design_index(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "WORKSPACES_DIR", tmp_path / "workspaces")
    monkeypatch.setattr(storage, "DESIGN_INDEX", tmp_path / "design_index.json")

    source = tmp_path / "plan.dxf"
    source.write_text("source", encoding="utf-8")
    project = Project(
        id="project-gone",
        name="plan.dxf",
        source_path=source,
        building=Building(id="project-gone"),
        designs=["DES-11111111", "DES-22222222"],
    )
    storage.save_project(project)
    for design_id in project.designs:
        storage.register_design(project.id, design_id)
        design_dir = storage.design_dir(project.id, design_id)
        design_dir.mkdir(parents=True, exist_ok=True)
        (design_dir / "design.json").write_text("{}", encoding="utf-8")

    assert storage.delete_project(project.id) is True
    assert not storage.workspace_dir(project.id).exists()
    assert storage.load_project(project.id) is None
    index = json.loads(storage.DESIGN_INDEX.read_text(encoding="utf-8"))
    assert "DES-11111111" not in index
    assert "DES-22222222" not in index
    assert storage.delete_project(project.id) is False


def test_delete_project_endpoint_removes_project_and_designs():
    project = _sample()
    design_ids = [_create_design(project), _create_design(project)]
    project_dir = storage.workspace_dir(project["project_id"])
    assert project_dir.exists()

    response = client.delete(f"/api/projects/{project['project_id']}")

    assert response.status_code == 204
    assert not project_dir.exists()
    assert client.get(f"/api/projects/{project['project_id']}").status_code == 404
    for design_id in design_ids:
        assert client.get(f"/api/designs/{design_id}").status_code == 404


def test_delete_design_endpoint_removes_design_and_files():
    project = _sample()
    design_id = _create_design(project)
    design_dir = storage.design_dir(project["project_id"], design_id)
    assert (design_dir / "design.json").exists()
    assert (design_dir / "preview.svg").exists()

    response = client.delete(f"/api/designs/{design_id}")

    assert response.status_code == 204
    assert not design_dir.exists()
    reloaded = client.get(f"/api/projects/{project['project_id']}").json()
    assert design_id not in {item["design_id"] for item in reloaded["designs"]}
    assert client.get(f"/api/designs/{design_id}").status_code == 404


def test_delete_design_cancels_active_turn_then_removes_files():
    project = _sample()
    design_id = _create_design(project)
    job = main_module.JOBS.create(project["project_id"], design_id)
    with main_module.STATE_LOCK:
        main_module.ACTIVE_TURNS[design_id] = job.id

    def finish_turn():
        assert job.cancel_requested.wait(2)
        time.sleep(0.05)
        with main_module.STATE_LOCK:
            main_module.ACTIVE_TURNS.pop(design_id, None)

    thread = threading.Thread(target=finish_turn)
    thread.start()
    try:
        response = client.delete(f"/api/designs/{design_id}")
        thread.join(timeout=3)
        assert response.status_code == 204
        assert job.cancel_requested.is_set()
        assert not storage.design_dir(
            project["project_id"], design_id
        ).exists()
    finally:
        thread.join(timeout=1)
        with main_module.STATE_LOCK:
            main_module.ACTIVE_TURNS.pop(design_id, None)


def test_delete_unknown_design_is_404():
    assert client.delete("/api/designs/DES-missing").status_code == 404
