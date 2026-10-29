from __future__ import annotations

import json

from agent.providers.base import ChatMessage, LLMProvider, LLMResponse, ToolCall


class FakeProvider(LLMProvider):
    """Offline provider.

    With queued responses it replays them (unit tests). Without a queue it runs a
    deterministic bathroom-agent policy over the tool results, so the full demo
    works with no API key.
    """

    name = "fake"
    model = "fake-scripted"

    def __init__(self, responses: list[LLMResponse] | None = None) -> None:
        self.responses = list(responses or [])
        self.calls: list[list[ChatMessage]] = []
        self._candidates: list[dict] = []
        self._candidate_index = 0
        self._applied = 0
        self._applied_ids: list[str] = []
        self._seq = 0

    def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
    ) -> LLMResponse:
        self.calls.append(list(messages))
        if self.responses:
            return self.responses.pop(0)
        return self._demo(messages)

    def _demo(self, messages: list[ChatMessage]) -> LLMResponse:
        tool_name, output = self._last_tool(messages)
        if tool_name is None:
            return self._call("inspect_plan", {})
        if tool_name == "inspect_plan":
            return self._call("list_layout_options", {})
        if tool_name == "list_layout_options":
            if "error" in output:
                return self._final(f"Could not list layouts: {output['error']}")
            self._candidates = output.get("candidates") or []
            if not self._candidates:
                return self._final("No layout candidates fit this room.")
            self._candidate_index = next(
                (
                    index
                    for index, candidate in enumerate(self._candidates)
                    if not candidate.get("violations")
                ),
                0,
            )
            return self._select_current()
        if tool_name == "select_layout":
            if "error" in output:
                return self._final(f"Could not select layout: {output['error']}")
            return self._call("route_drainage", {})
        if tool_name == "route_drainage":
            if "error" in output:
                if self._candidate_index + 1 < len(self._candidates):
                    self._candidate_index += 1
                    return self._select_current()
                return self._final(
                    "No generated layout could be routed to the stack. "
                    "A human decision is needed: move the stack or relax the room constraints."
                )
            return self._call("validate_design", {})
        if tool_name == "validate_design":
            fixes = output.get("fixes") or []
            if fixes and self._applied < 2:
                fix = next(
                    (item for item in fixes if item.get("kind") == "SELECT_CANDIDATE"),
                    fixes[0],
                )
                if fix["id"] not in self._applied_ids:
                    self._applied += 1
                    self._applied_ids.append(fix["id"])
                    return self._call("apply_fix", {"fix_id": fix["id"]})
            return self._call("explain_design", {})
        if tool_name == "apply_fix":
            if "error" in output:
                return self._final(f"Could not apply the fix: {output['error']}")
            return self._call("validate_design", {})
        if tool_name == "explain_design":
            explanation = output.get("explanation") or "Design complete."
            return self._final(explanation)
        return self._final("Fake provider stopped.")

    def _select_current(self) -> LLMResponse:
        candidate = self._candidates[self._candidate_index]
        hint = (candidate.get("rationale_hint") or "best ranked candidate").rstrip(".")
        rationale = (
            f"Selected {candidate['pattern']} layout {candidate['id']}: {hint}."
        )
        return self._call(
            "select_layout",
            {"candidate_id": candidate["id"], "rationale": rationale},
        )

    def _last_tool(self, messages: list[ChatMessage]) -> tuple[str | None, dict]:
        for message in reversed(messages):
            if message.role != "tool":
                continue
            try:
                output = json.loads(message.content or "{}")
            except (TypeError, json.JSONDecodeError):
                output = {}
            return message.name, output if isinstance(output, dict) else {"result": output}
        return None, {}

    def _call(self, name: str, arguments: dict) -> LLMResponse:
        self._seq += 1
        return LLMResponse(
            content=None,
            tool_calls=[ToolCall(id=f"fake-{self._seq}", name=name, arguments=arguments)],
            model=self.model,
            provider=self.name,
        )

    def _final(self, content: str) -> LLMResponse:
        return LLMResponse(
            content=content,
            tool_calls=[],
            model=self.model,
            provider=self.name,
        )
