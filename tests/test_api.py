import time

import pytest
from fastapi.testclient import TestClient

from app.main import app

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
