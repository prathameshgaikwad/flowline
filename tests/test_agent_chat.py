from agent.loop import AgentRunner
from agent.providers.base import ChatMessage, LLMProvider, LLMResponse, ToolCall
from agent.providers.fake import FakeProvider
from agent.tools import TOOLS, AgentSession
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


def test_design_turn_emits_plan_decisions_and_reasoning(tmp_path):
    session = make_session(tmp_path)
    events = []
    provider = FakeProvider()
    runner = AgentRunner(provider, on_event=events.append)
    result = runner.run("Design the bathroom.", session)

    assert result.stopped_reason == "final"
    assert session.design is not None
    assert session.plan
    assert {step["id"] for step in session.plan} >= {"inspect", "select", "validate"}
    assert any(event["type"] == "decision" for event in events)
    decisions = [event["decision"] for event in events if event["type"] == "decision"]
    assert any(decision["kind"] == "layout_selected" for decision in decisions)
    assert any(decision["kind"] == "validation" for decision in decisions)
    selected = next(decision for decision in decisions if decision["kind"] == "layout_selected")
    assert selected["rejected"]
    assert all("reason" in item for item in selected["rejected"])


class ScriptedProvider(LLMProvider):
    name = "scripted"
    model = "scripted"

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat(self, messages, tools=None, tool_choice=None):
        self.calls.append(list(messages))
        return self.responses.pop(0)


def tool_call(name, arguments=None):
    return ToolCall(id=f"call-{name}", name=name, arguments=arguments or {})


def test_follow_up_question_uses_compare_tool_and_history(tmp_path):
    session = make_session(tmp_path)
    AgentRunner(FakeProvider()).run("Design the bathroom.", session)
    history = [
        ChatMessage(role="user", content="Design the bathroom."),
        ChatMessage(role="assistant", content="Design complete."),
    ]
    provider = ScriptedProvider(
        [
            LLMResponse(
                content=None,
                tool_calls=[tool_call("compare_layouts")],
                model="scripted",
                provider="scripted",
                reasoning="The user asked why alternatives were rejected.",
            ),
            LLMResponse(
                content="C-02 was selected because it had the best score; the others are listed in the comparison.",
                tool_calls=[],
                model="scripted",
                provider="scripted",
            ),
        ]
    )
    events = []
    result = AgentRunner(provider, on_event=events.append).run_turn(
        "Why did you reject the other layouts?", session, history=history
    )
    assert result.stopped_reason == "final"
    assert result.history[0]["tool"] == "compare_layouts"
    assert any(event["type"] == "reasoning" for event in events)
    first_messages = provider.calls[0]
    assert any(message.role == "user" and message.content == "Design the bathroom." for message in first_messages)


def test_set_fixtures_resets_design(tmp_path):
    session = make_session(tmp_path)
    AgentRunner(FakeProvider()).run("Design the bathroom.", session)
    assert session.design is not None
    result = TOOLS["set_fixtures"].run({"fixtures": ["WC", "BASIN"]}, session)
    assert result["fixtures"] == ["WC", "BASIN"]
    assert session.design is None
    assert session.candidates == []
    assert session.fixture_types == [FixtureType.WC, FixtureType.BASIN]
    assert any(decision["kind"] == "fixtures_changed" for decision in session.decisions)


def test_get_design_state_and_compare_layouts(tmp_path):
    session = make_session(tmp_path)
    AgentRunner(FakeProvider()).run("Design the bathroom.", session)
    state = TOOLS["get_design_state"].run({}, session)
    assert state["design"]["layout_id"]
    assert state["validation"]["counts"]["ERROR"] == 0
    assert state["decisions"]
    comparison = TOOLS["compare_layouts"].run({}, session)
    assert comparison["selected_id"]
    assert len(comparison["candidates"]) >= len(session.candidates)
    assert all("reason" in item for item in comparison["candidates"])
