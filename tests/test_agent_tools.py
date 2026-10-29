import pytest

from agent.tools import TOOLS, AgentSession, ToolError, tool_schemas
from core.dxf_import import import_dxf
from core.models import FixtureType, Stack
from core.sample_plan import build_apartment


def make_session(tmp_path):
    path = tmp_path / "apartment.dxf"
    build_apartment(path)
    building = import_dxf(path)
    return AgentSession(
        building=building,
        source_path=path,
        out_dir=tmp_path / "out",
        room_id="R-01",
        fixture_types=[FixtureType.WC, FixtureType.BASIN, FixtureType.SHOWER],
        stack=Stack(id="S1", position=building.shafts[0].position),
        profile_id="india_nbc_2016",
    )


def test_tool_schemas_are_valid():
    schemas = tool_schemas()
    names = {schema["function"]["name"] for schema in schemas}
    assert {
        "inspect_plan",
        "list_layout_options",
        "select_layout",
        "route_drainage",
        "validate_design",
        "apply_fix",
        "explain_design",
    } <= names
    for schema in schemas:
        assert schema["type"] == "function"
        assert schema["function"]["parameters"]["type"] == "object"


def test_full_tool_sequence(tmp_path):
    session = make_session(tmp_path)
    plan = TOOLS["inspect_plan"].run({}, session)
    assert plan["rooms"][0]["name"] == "BATHROOM"
    assert plan["selection"]["room_id"] == "R-01"

    options = TOOLS["list_layout_options"].run({}, session)
    assert options["count"] >= 3
    assert session.candidates

    candidate_id = options["candidates"][0]["id"]
    selected = TOOLS["select_layout"].run(
        {"candidate_id": candidate_id, "rationale": "Best ranked layout."}, session
    )
    assert selected["layout_id"] == candidate_id
    assert session.design is not None

    routed = TOOLS["route_drainage"].run({}, session)
    assert routed["count"] == 3

    validated = TOOLS["validate_design"].run({}, session)
    assert validated["counts"]["ERROR"] == 0
    assert any(issue["source"] for issue in validated["issues"])

    explained = TOOLS["explain_design"].run({}, session)
    assert explained["explanation"]
    assert explained["counts"]["ERROR"] == 0


def test_unknown_candidate_is_rejected(tmp_path):
    session = make_session(tmp_path)
    TOOLS["list_layout_options"].run({}, session)
    with pytest.raises(ToolError, match="Unknown candidate"):
        TOOLS["select_layout"].run(
            {"candidate_id": "C-99", "rationale": "because"}, session
        )


def test_select_requires_rationale(tmp_path):
    session = make_session(tmp_path)
    options = TOOLS["list_layout_options"].run({}, session)
    with pytest.raises(ToolError, match="rationale"):
        TOOLS["select_layout"].run(
            {"candidate_id": options["candidates"][0]["id"]}, session
        )


def test_apply_fix_reduces_warnings(tmp_path):
    session = make_session(tmp_path)
    TOOLS["list_layout_options"].run({}, session)
    candidate_id = session.candidates[0].id
    TOOLS["select_layout"].run(
        {"candidate_id": candidate_id, "rationale": "Top ranked layout."}, session
    )
    TOOLS["route_drainage"].run({}, session)
    first = TOOLS["validate_design"].run({}, session)
    assert first["fixes"]
    updated = TOOLS["apply_fix"].run({"fix_id": first["fixes"][0]["id"]}, session)
    assert updated["counts"]["ERROR"] <= first["counts"]["ERROR"]
    assert session.applied_fixes


def test_export_requires_approval_then_writes_dxf(tmp_path):
    session = make_session(tmp_path)
    TOOLS["list_layout_options"].run({}, session)
    TOOLS["select_layout"].run(
        {"candidate_id": session.candidates[0].id, "rationale": "Top ranked layout."},
        session,
    )
    TOOLS["route_drainage"].run({}, session)
    with pytest.raises(ToolError, match="approval"):
        TOOLS["export_dxf"].run({}, session)

    session.approved = True
    result = TOOLS["export_dxf"].run({}, session)
    assert result["path"].endswith(".dxf")
    assert session.exported_path == result["path"]
    assert (tmp_path / "out").exists()


def test_profile_switch(tmp_path):
    session = make_session(tmp_path)
    TOOLS["list_layout_options"].run({}, session)
    TOOLS["select_layout"].run(
        {"candidate_id": session.candidates[0].id, "rationale": "Top ranked layout."},
        session,
    )
    TOOLS["route_drainage"].run({}, session)
    result = TOOLS["validate_design"].run({"profile_id": "us_ipc_2021"}, session)
    assert result["profile_id"] == "us_ipc_2021"
    assert session.profile_id == "us_ipc_2021"
