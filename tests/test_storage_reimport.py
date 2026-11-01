import json

from app import storage
from core.dxf_import import PARSER_VERSION
from core.models import Building
from core.sample_plan import build_apartment


def test_old_designless_workspace_is_reimported(tmp_path, monkeypatch):
    workspaces = tmp_path / "workspaces"
    monkeypatch.setattr(storage, "WORKSPACES_DIR", workspaces)

    project_dir = workspaces / "old"
    project_dir.mkdir(parents=True)
    source = project_dir / "apartment.dxf"
    build_apartment(source)
    old = {
        "id": "old",
        "name": "apartment.dxf",
        "source_file": source.name,
        "building": Building(id="old").model_dump(mode="json"),
        "designs": [],
        "created_at": 1.0,
        "updated_at": 1.0,
    }
    (project_dir / "workspace.json").write_text(json.dumps(old), encoding="utf-8")

    project = storage.load_project("old")

    assert project is not None
    assert len(project.building.rooms) == 3
    saved = json.loads((project_dir / "workspace.json").read_text(encoding="utf-8"))
    assert saved["parser_version"] == PARSER_VERSION


def test_old_workspace_with_designs_is_reimported_without_losing_designs(
    tmp_path, monkeypatch
):
    workspaces = tmp_path / "workspaces"
    monkeypatch.setattr(storage, "WORKSPACES_DIR", workspaces)

    project_dir = workspaces / "old"
    project_dir.mkdir(parents=True)
    source = project_dir / "apartment.dxf"
    build_apartment(source)
    old = {
        "id": "old",
        "name": "apartment.dxf",
        "source_file": source.name,
        "building": Building(id="old").model_dump(mode="json"),
        "designs": ["DES-old"],
        "created_at": 1.0,
        "updated_at": 1.0,
    }
    (project_dir / "workspace.json").write_text(json.dumps(old), encoding="utf-8")

    project = storage.load_project("old")

    assert project is not None
    assert project.designs == ["DES-old"]
    assert len(project.building.rooms) == 3
    assert len(project.building.shafts) >= 1
    saved = json.loads((project_dir / "workspace.json").read_text(encoding="utf-8"))
    assert saved["parser_version"] == PARSER_VERSION
