import time

import ezdxf
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _mixed_plan(tmp_path):
    path = tmp_path / "mixed_plan.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    for name in ("A-ROOM", "A-TEXT", "A-SHAFT", "A-DOOR"):
        doc.layers.add(name)
    msp = doc.modelspace()

    def room(x1, y1, x2, y2, label):
        msp.add_lwpolyline(
            [(x1, y1), (x2, y1), (x2, y2), (x1, y2)],
            close=True,
            dxfattribs={"layer": "A-ROOM"},
        )
        msp.add_text(
            label, dxfattribs={"layer": "A-TEXT", "height": 150}
        ).set_placement(((x1 + x2) / 2, (y1 + y2) / 2))

    room(0, 0, 2400, 1800, "BATHROOM")
    room(0, 2000, 2400, 4000, "KITCHEN")
    room(2600, 0, 5000, 1800, "BALCONY")
    room(2600, 2000, 5000, 4000, "BEDROOM")
    msp.add_lwpolyline(
        [(2450, 150), (2650, 150), (2650, 450), (2450, 450)],
        close=True,
        dxfattribs={"layer": "A-SHAFT"},
    )
    msp.add_text(
        "SHAFT", dxfattribs={"layer": "A-TEXT", "height": 80}
    ).set_placement((2550, 300))
    msp.add_line((2200, 0), (2200, 900), dxfattribs={"layer": "A-DOOR"})
    doc.saveas(path)
    return path


def _wait(job_id: str) -> dict:
    for _ in range(500):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["done"]:
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_bathroom_kitchen_and_balcony_become_one_design(tmp_path):
    path = _mixed_plan(tmp_path)
    upload = client.post(
        "/api/projects",
        files={"file": ("mixed_plan.dxf", path.read_bytes(), "application/dxf")},
    )
    assert upload.status_code == 200, upload.text
    project = upload.json()
    rooms = {
        room["name"]: room
        for room in project["rooms"]
        if room["plumbing_role"] != "none"
    }
    assert set(rooms) == {"BATHROOM", "KITCHEN", "BALCONY"}

    started = client.post(
        f"/api/projects/{project['project_id']}/design",
        json={
            "rooms": [
                {
                    "room_id": room["id"],
                    "fixtures": room["default_fixtures"],
                    "stack_id": room["default_stack_id"],
                }
                for room in rooms.values()
            ],
            "provider": "fake",
            "profile_id": "india_nbc_2016",
        },
    )
    assert started.status_code == 200, started.text
    job = _wait(started.json()["job_id"])
    assert job["status"] == "done", job
    result = job["result"]
    assert result["counts"]["ERROR"] == 0, result["issues"]
    assert set(result["room_ids"]) == {room["id"] for room in rooms.values()}
    assert result["sheet_ready"] is True
    assert len(result["design"]["room_plans"]) == 3
