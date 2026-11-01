import time

import ezdxf
import pytest
from fastapi.testclient import TestClient

from app.main import DESIGNS, _project_payload, app
from app.models import Project
from core.dxf_import import import_dxf
from core.models import DrawingCheck, Severity, ValidationResult

client = TestClient(app)


@pytest.fixture(autouse=True)
def force_fake_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fake")

def _sample():
    response = client.post("/api/projects/sample", params={"name": "apartment"})
    assert response.status_code == 200, response.text
    return response.json()


def test_health_and_profiles():
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["provider"] == "fake"
    profiles = client.get("/api/profiles").json()["profiles"]
    assert {item["id"] for item in profiles} == {"india_nbc_2016", "us_ipc_2021"}


def test_sample_project():
    data = _sample()
    assert data["project_id"]
    assert len(data["rooms"]) >= 3
    assert data["svg"].startswith("<svg")
    assert data["shafts"]


def test_project_payload_exposes_detected_fixtures_and_shaft_services(tmp_path):
    path = tmp_path / "fixture_plan.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (2400, 0), (2400, 1800), (0, 1800)],
        close=True,
        dxfattribs={"layer": "A-ROOM"},
    )
    msp.add_text(
        "BATHROOM", dxfattribs={"layer": "A-TEXT", "height": 150}
    ).set_placement((1200, 900))
    msp.add_lwpolyline(
        [(2500, 0), (3100, 0), (3100, 600), (2500, 600)],
        close=True,
        dxfattribs={"layer": "A-SHAFT"},
    )
    wc = doc.blocks.new("A$C_WC")
    wc.add_lwpolyline(
        [(-325, -275), (325, -275), (325, 275), (-325, 275)],
        close=True,
    )
    msp.add_blockref(
        "A$C_WC",
        (700, 900),
        dxfattribs={"layer": "M03 Sanitaryware"},
    )
    doc.saveas(path)
    project = Project(
        id="fixture-project",
        name="fixture_plan.dxf",
        source_path=path,
        building=import_dxf(path),
    )

    data = _project_payload(project)

    assert data["rooms"][0]["fixtures"][0]["type"] == "WC"
    assert data["shafts"][0]["services"] == ["DRAIN", "WATER", "VENT"]
    assert data["stacks"][0]["shaft_id"] == data["shafts"][0]["id"]
    assert data["water_sources"][0]["shaft_id"] == data["shafts"][0]["id"]


def test_upload_and_reject_non_dxf():
    sample = _sample()
    del sample  # only used to ensure the endpoint is warm
    bad = client.post(
        "/api/projects",
        files={"file": ("plan.txt", b"not a drawing", "text/plain")},
    )
    assert bad.status_code == 400


def test_full_design_and_approval_flow():
    project = _sample()
    bathroom = next(room for room in project["rooms"] if room["wet_area"])
    start = client.post(
        f"/api/projects/{project['project_id']}/design",
        json={
            "room_id": bathroom["id"],
            "fixtures": ["WC", "BASIN", "SHOWER"],
            "provider": "fake",
            "profile_id": "india_nbc_2016",
        },
    )
    assert start.status_code == 200, start.text
    job_id = start.json()["job_id"]
    design_id = start.json()["design_id"]

    for _ in range(200):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["done"]:
            break
        time.sleep(0.05)
    assert job["done"], job
    assert job["status"] == "done", job
    result = job["result"]
    assert result["counts"]["ERROR"] == 0
    assert result["design_id"] == design_id
    assert result["design"]

    design = client.get(f"/api/designs/{design_id}")
    assert design.status_code == 200
    assert design.json()["svg"].startswith("<svg")
    assert design.json()["sheet_ready"] is True
    assert design.json()["sheet_pages"] >= 1
    assert design.json()["drawing_review"]

    sheet = client.get(f"/api/designs/{design_id}/sheet.svg")
    assert sheet.status_code == 200
    assert b"<svg" in sheet.content
    pdf = client.get(f"/api/designs/{design_id}/sheet.pdf")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")

    resized = client.patch(
        f"/api/designs/{design_id}/sheet",
        json={"preset": "A4", "orientation": "landscape"},
    )
    assert resized.status_code == 200, resized.text
    assert resized.json()["sheet"]["preset"] == "A4"
    assert resized.json()["sheet_pages"] == 2

    approve = client.post(
        f"/api/designs/{design_id}/approve",
        json={"approver_name": "Test Engineer"},
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["download_url"]

    download = client.get(f"/api/designs/{design_id}/download.dxf")
    assert download.status_code == 200
    assert b"SECTION" in download.content


def test_unknown_job_is_404():
    assert client.get("/api/jobs/nope").status_code == 404


def test_approval_exports_with_validation_and_drawing_errors():
    project = _sample()
    bathroom = next(room for room in project["rooms"] if room["wet_area"])
    start = client.post(
        f"/api/projects/{project['project_id']}/design",
        json={
            "room_id": bathroom["id"],
            "fixtures": ["WC", "BASIN", "SHOWER"],
            "provider": "fake",
            "profile_id": "india_nbc_2016",
        },
    )
    assert start.status_code == 200, start.text
    job_id = start.json()["job_id"]
    design_id = start.json()["design_id"]
    for _ in range(200):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["done"]:
            break
        time.sleep(0.05)
    assert job["done"], job

    session = DESIGNS[design_id]
    session.validation.append(
        ValidationResult(
            rule_id="TEST_DESIGN_ERROR",
            severity=Severity.ERROR,
            message="Deliberate test design error.",
            source="Test",
        )
    )
    session.drawing_review.append(
        DrawingCheck(
            rule_id="TEST_DRAWING_ERROR",
            severity=Severity.ERROR,
            message="Deliberate test drawing error.",
        )
    )
    if session.design is not None:
        session.design.route_failures = ["Deliberate test route failure."]

    approve = client.post(
        f"/api/designs/{design_id}/approve",
        json={"approver_name": "Test Engineer"},
    )
    assert approve.status_code == 200, approve.text
    payload = approve.json()
    assert payload["counts"]["ERROR"] >= 1
    assert any(item["rule_id"] == "TEST_DESIGN_ERROR" for item in payload["validation"])
    assert any(
        item["rule_id"] == "TEST_DRAWING_ERROR"
        for item in payload["drawing_review"]
    )
    assert payload["download_url"]
    download = client.get(f"/api/designs/{design_id}/download.dxf")
    assert download.status_code == 200
