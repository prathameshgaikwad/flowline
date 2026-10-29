from __future__ import annotations

from agent.providers.base import ChatMessage, LLMProvider, LLMResponse


class FakeProvider(LLMProvider):
    """Offline provider. Returns queued responses for tests and scripted demos."""

    name = "fake"
    model = "fake-scripted"

    def __init__(self, responses: list[LLMResponse] | None = None) -> None:
        self.responses = list(responses or [])
        self.calls: list[list[ChatMessage]] = []

    def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
    ) -> LLMResponse:
        self.calls.append(list(messages))
        if self.responses:
            return self.responses.pop(0)
        return LLMResponse(
            content="Fake provider ready. No scripted response remains.",
            tool_calls=[],
            model=self.model,
            provider=self.name,
        )
