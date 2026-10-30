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
        self._intent: str | None = None

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
        if self._intent is None:
            self._intent = self._detect_intent(messages)
        tool_name, output = self._last_tool(messages)
        if tool_name is None:
            if self._intent == "validate":
                args = {}
                profile = self._profile_from_text(self._last_user_text(messages))
                if profile:
                    args["profile_id"] = profile
                return self._call("validate_design", args)
            if self._intent == "compare":
                return self._call("compare_layouts", {})
            if self._intent == "fix":
                return self._call("validate_design", {})
            if self._intent == "state":
                return self._call("get_design_state", {})
            return self._call("inspect_plan", {})
        if tool_name == "compare_layouts":
            return self._final(self._comparison_text(output))
        if tool_name == "get_design_state":
            return self._final(self._state_text(output))
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
            if self._intent == "validate":
                return self._final(self._validation_text(output))
            if self._intent == "fix":
                fixes = output.get("fixes") or []
                if fixes:
                    return self._call("apply_fix", {"fix_id": fixes[0]["id"]})
                return self._final(self._validation_text(output))
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
            if self._intent == "fix":
                return self._final(
                    f"Applied fix {output.get('applied')}. "
                    f"Revalidated: {output.get('counts')}."
                )
            return self._call("validate_design", {})
        if tool_name == "explain_design":
            explanation = output.get("explanation") or "Design complete."
            return self._final(explanation)
        return self._final("Fake provider stopped.")

    def _detect_intent(self, messages: list[ChatMessage]) -> str:
        text = self._last_user_text(messages).lower().strip()
        if (
            text.startswith("design")
            or "design the" in text
            or "new design" in text
            or "re-run" in text
            or "rerun" in text
            or "another layout" in text
            or "try a different layout" in text
        ):
            return "design"
        if any(word in text for word in ("validate", "revalidate", "standard", "ipc", "nbc")):
            return "validate"
        if "fix" in text:
            return "fix"
        if any(word in text for word in ("state", "status", "summary", "what changed")):
            return "state"
        if any(word in text for word in ("why", "compare", "reject", "alternative", "explain")):
            return "compare"
        return "design"

    def _last_user_text(self, messages: list[ChatMessage]) -> str:
        for message in reversed(messages):
            if message.role == "user" and message.content:
                return message.content
        return ""

    def _profile_from_text(self, text: str) -> str | None:
        lowered = text.lower()
        if any(word in lowered for word in ("us", "ipc", "american")):
            return "us_ipc_2021"
        if any(word in lowered for word in ("india", "nbc", "is 1742")):
            return "india_nbc_2016"
        return None

    def _validation_text(self, output: dict) -> str:
        counts = output.get("counts") or {}
        issues = output.get("issues") or []
        return (
            f"Validated against {output.get('profile_id')}: "
            f"{counts.get('PASS', 0)} PASS, {counts.get('WARNING', 0)} WARNING, "
            f"{counts.get('ERROR', 0)} ERROR. "
            f"{len(issues)} non-pass result(s)."
        )

    def _comparison_text(self, output: dict) -> str:
        selected = output.get("selected_id")
        rows = output.get("candidates") or []
        rejected = [row for row in rows if not row.get("selected")]
        return (
            f"Selected {selected} ({output.get('selected_pattern')}). "
            f"Rejected {len(rejected)} alternative(s): "
            + "; ".join(
                f"{row.get('id')}: {row.get('reason')}" for row in rejected[:5]
            )
        )

    def _state_text(self, output: dict) -> str:
        design = output.get("design") or {}
        counts = (output.get("validation") or {}).get("counts") or {}
        return (
            f"Current layout {design.get('layout_id')} with "
            f"{len(design.get('fixtures') or [])} fixtures and "
            f"{len(design.get('pipes') or [])} pipes. "
            f"Validation: {counts.get('PASS', 0)} PASS, "
            f"{counts.get('WARNING', 0)} WARNING, {counts.get('ERROR', 0)} ERROR."
        )

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
