import time

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _wait_job(job_id: str) -> dict:
    for _ in range(300):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["done"]:
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def _project():
    response = client.post("/api/projects/sample", params={"name": "apartment"})
    assert response.status_code == 200, response.text
    return response.json()


def test_design_chat_turns_and_reload():
    project = _project()
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
    data = created.json()
    design_id = data["design_id"]
    assert data["messages"] == []
    assert data["design"] is None

    first = client.post(
        f"/api/designs/{design_id}/messages",
        json={"content": "Design the bathroom drainage."},
    )
    assert first.status_code == 200, first.text
    job = _wait_job(first.json()["job_id"])
    assert job["status"] == "done", job
    result = job["result"]
    assert result["counts"]["ERROR"] == 0
    assert result["design"]["layout_id"]
    assert result["plan"]
    assert result["decisions"]

    reloaded = client.get(f"/api/designs/{design_id}").json()
    assert len(reloaded["messages"]) == 2
    assert reloaded["events"]
    assert reloaded["design"]["layout_id"] == result["design"]["layout_id"]
    assert any(item["kind"] == "layout_selected" for item in reloaded["decisions"])

    second = client.post(
        f"/api/designs/{design_id}/messages",
        json={"content": "Why did you reject the other layouts?"},
    )
    assert second.status_code == 200, second.text
    job = _wait_job(second.json()["job_id"])
    assert job["status"] == "done", job
    events = client.get(f"/api/designs/{design_id}/events").json()["events"]
    assert any(
        event.get("type") == "tool_result"
        and event.get("tool") == "compare_layouts"
        for event in events
    )
    assert "Rejected" in job["result"]["final_answer"]


def test_standard_change_marks_stale_and_blocks_approval():
    project = _project()
    bathroom = next(room for room in project["rooms"] if room["wet_area"])
    created = client.post(
        f"/api/projects/{project['project_id']}/designs",
        json={
            "room_id": bathroom["id"],
            "fixtures": ["WC", "BASIN", "SHOWER"],
            "shaft_id": project["shafts"][0]["id"],
            "profile_id": "india_nbc_2016",
        },
    ).json()
    design_id = created["design_id"]
    job = _wait_job(
        client.post(
            f"/api/designs/{design_id}/messages",
            json={"content": "Design the bathroom."},
        ).json()["job_id"]
    )
    assert job["result"]["counts"]["ERROR"] == 0

    changed = client.patch(
        f"/api/designs/{design_id}", json={"profile_id": "us_ipc_2021"}
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["profile_id"] == "us_ipc_2021"
    assert changed.json()["stale"] is True

    approve = client.post(
        f"/api/designs/{design_id}/approve",
        json={"approver_name": "Test Engineer"},
    )
    assert approve.status_code == 409
