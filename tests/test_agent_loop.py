from agent.loop import AgentRunner
from agent.providers.base import LLMError, LLMProvider, LLMResponse, ToolCall
from agent.providers.fake import FakeProvider
from agent.tools import AgentSession
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
    )


def test_fake_agent_completes_the_workflow(tmp_path):
    session = make_session(tmp_path)
    events = []
    runner = AgentRunner(FakeProvider(), on_event=events.append)
    result = runner.run("Design the bathroom drainage.", session)

    assert result.stopped_reason == "final"
    assert session.design is not None
    assert len(session.design.pipes) == 3
    tools = [item["tool"] for item in result.history]
    assert "inspect_plan" in tools
    assert "list_layout_options" in tools
    assert "select_layout" in tools
    assert "route_drainage" in tools
    assert "validate_design" in tools
    assert "explain_design" in tools
    assert any(event["type"] == "final" for event in events)
    assert any(event["type"] == "tool_result" for event in events)


def test_fake_agent_uses_the_us_profile(tmp_path):
    session = make_session(tmp_path)
    session.profile_id = "us_ipc_2021"
    runner = AgentRunner(FakeProvider())
    result = runner.run("Design the bathroom drainage with the US profile.", session)
    assert result.stopped_reason == "final"
    assert session.design is not None
    diameters = {pipe.from_node.split("-")[0]: pipe.diameter_mm for pipe in session.design.pipes}
    assert diameters["WC"] == 76
    assert diameters["BASIN"] == 32
    assert diameters["SHOWER"] == 50


def test_repeat_guard(tmp_path):
    session = make_session(tmp_path)
    responses = [
        LLMResponse(
            content=None,
            tool_calls=[ToolCall(id="1", name="inspect_plan", arguments={})],
            model="fake",
            provider="fake",
        )
        for _ in range(4)
    ]
    result = AgentRunner(FakeProvider(responses), max_iterations=6).run(
        "loop", session
    )
    assert result.stopped_reason == "loop"


class ErrorProvider(LLMProvider):
    name = "error"
    model = "error"

    def chat(self, messages, tools=None, tool_choice=None):
        raise LLMError("boom")


def test_provider_error_is_reported(tmp_path):
    session = make_session(tmp_path)
    result = AgentRunner(ErrorProvider()).run("test", session)
    assert result.stopped_reason == "error"
    assert "provider error" in result.final_answer


class UnknownToolProvider(LLMProvider):
    name = "unknown"
    model = "unknown"

    def __init__(self):
        self.calls = 0

    def chat(self, messages, tools=None, tool_choice=None):
        self.calls += 1
        if self.calls == 1:
            return LLMResponse(
                content=None,
                tool_calls=[ToolCall(id="1", name="not_a_tool", arguments={})],
                model=self.model,
                provider=self.name,
            )
        return LLMResponse(
            content="Stopped after the tool error.",
            tool_calls=[],
            model=self.model,
            provider=self.name,
        )


def test_unknown_tool_is_returned_to_the_model(tmp_path):
    session = make_session(tmp_path)
    result = AgentRunner(UnknownToolProvider()).run("test", session)
    assert result.history[0]["success"] is False
    assert "Unknown tool" in result.history[0]["output"]["error"]
    assert result.stopped_reason == "final"
