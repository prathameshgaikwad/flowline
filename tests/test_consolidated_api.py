import time

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _wait(job_id: str) -> dict:
    for _ in range(400):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["done"]:
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def _project():
    response = client.post("/api/projects/sample", params={"name": "apartment"})
    assert response.status_code == 200, response.text
    return response.json()


def _room_payload(project):
    bathroom = next(room for room in project["rooms"] if room["name"] == "BATHROOM")
    kitchen = next(room for room in project["rooms"] if room["name"] == "KITCHEN")
    return [
        {
            "room_id": bathroom["id"],
            "fixtures": bathroom["default_fixtures"],
            "stack_id": bathroom["default_stack_id"],
        },
        {
            "room_id": kitchen["id"],
            "fixtures": kitchen["default_fixtures"],
            "stack_id": kitchen["default_stack_id"],
        },
    ]


def test_creates_and_runs_one_consolidated_design():
    project = _project()
    rooms = _room_payload(project)

    created = client.post(
        f"/api/projects/{project['project_id']}/designs",
        json={
            "rooms": rooms,
            "provider": "fake",
            "profile_id": "india_nbc_2016",
        },
    )
    assert created.status_code == 200, created.text
    created_data = created.json()
    assert created_data["room_ids"] == [item["room_id"] for item in rooms]
    assert len(created_data["room_plans"]) == 2
    assert created_data["stacks"]
    design_id = created_data["design_id"]

    started = client.post(
        f"/api/projects/{project['project_id']}/design",
        json={
            "rooms": rooms,
            "provider": "fake",
            "profile_id": "india_nbc_2016",
        },
    )
    assert started.status_code == 200, started.text
    job = _wait(started.json()["job_id"])
    assert job["status"] == "done", job
    result = job["result"]
    assert result["counts"]["ERROR"] == 0, result["issues"]
    assert result["room_ids"] == [item["room_id"] for item in rooms]
    assert len(result["design"]["room_plans"]) == 2
    assert result["sheet_ready"] is True
    assert len(result["stacks"]) == 1

    reloaded = client.get(f"/api/designs/{result['design_id']}")
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["room_ids"] == result["room_ids"]
    assert len(reloaded.json()["room_plans"]) == 2

    sheet = client.get(f"/api/designs/{result['design_id']}/sheet.svg")
    assert sheet.status_code == 200
    approve = client.post(
        f"/api/designs/{result['design_id']}/approve",
        json={"approver_name": "Test Engineer"},
    )
    assert approve.status_code == 200, approve.text
    download = client.get(f"/api/designs/{result['design_id']}/download.dxf")
    assert download.status_code == 200
    assert design_id != result["design_id"]


def test_rejects_duplicate_rooms():
    project = _project()
    room = _room_payload(project)[0]
    response = client.post(
        f"/api/projects/{project['project_id']}/designs",
        json={
            "rooms": [room, room],
            "provider": "fake",
            "profile_id": "india_nbc_2016",
        },
    )
    assert response.status_code == 400
    assert "more than once" in response.text


def test_legacy_single_room_request_still_works():
    project = _project()
    bathroom = next(room for room in project["rooms"] if room["name"] == "BATHROOM")
    created = client.post(
        f"/api/projects/{project['project_id']}/designs",
        json={
            "room_id": bathroom["id"],
            "fixtures": bathroom["default_fixtures"],
            "shaft_id": project["shafts"][0]["id"],
            "provider": "fake",
            "profile_id": "india_nbc_2016",
        },
    )
    assert created.status_code == 200, created.text
    data = created.json()
    assert data["room_ids"] == [bathroom["id"]]
    assert len(data["room_plans"]) == 1
