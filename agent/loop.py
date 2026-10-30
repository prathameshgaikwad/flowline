from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable

from agent.logging import ActionLogger
from agent.prompt import SYSTEM_PROMPT, build_context
from agent.providers.base import ChatMessage, LLMError, LLMProvider
from agent.tools import TOOLS, AgentSession, ToolError, tool_schemas

EventCallback = Callable[[dict], None]

TOOL_STEP = {
    "inspect_plan": "inspect",
    "list_layout_options": "layouts",
    "select_layout": "select",
    "route_drainage": "route",
    "validate_design": "validate",
    "apply_fix": "fix",
    "explain_design": "explain",
}


class AgentResult:
    def __init__(
        self,
        final_answer: str,
        iterations: int,
        history: list[dict],
        stopped_reason: str,
        session: AgentSession,
    ) -> None:
        self.final_answer = final_answer
        self.iterations = iterations
        self.history = history
        self.stopped_reason = stopped_reason
        self.session = session


class AgentRunner:
    def __init__(
        self,
        provider: LLMProvider,
        *,
        max_iterations: int = 12,
        logger: ActionLogger | None = None,
        on_event: EventCallback | None = None,
    ) -> None:
        self.provider = provider
        self.max_iterations = max_iterations
        self.logger = logger or ActionLogger()
        self.on_event = on_event

    def run(
        self,
        request: str,
        session: AgentSession,
        request_id: str | None = None,
    ) -> AgentResult:
        return self.run_turn(request, session, history=None, request_id=request_id)

    def run_turn(
        self,
        request: str,
        session: AgentSession,
        *,
        history: list[ChatMessage] | None = None,
        request_id: str | None = None,
    ) -> AgentResult:
        request_id = request_id or uuid.uuid4().hex[:8]
        tool_history: list[dict] = []
        conversation = [
            message
            for message in (history or [])
            if message.role in ("user", "assistant") and (message.content or "").strip()
        ]
        messages = [
            ChatMessage(
                role="system",
                content=SYSTEM_PROMPT + "\n\n" + build_context(session),
            ),
            *conversation[-12:],
            ChatMessage(role="user", content=request),
        ]
        session.ensure_plan()
        self._emit(
            {
                "type": "turn_start",
                "request": request,
                "request_id": request_id,
                "plan": session.plan,
            }
        )
        self._emit({"type": "plan", "steps": session.plan})

        last_key: str | None = None
        repeat_count = 0
        iterations = 0
        while iterations < self.max_iterations:
            iterations += 1
            try:
                response = self.provider.chat(messages, tools=tool_schemas())
            except LLMError as exc:
                return self._finish(
                    f"Stopped: provider error: {exc}",
                    iterations,
                    tool_history,
                    "error",
                    session,
                    request_id,
                )
            except Exception as exc:
                return self._finish(
                    f"Stopped: unexpected provider error ({type(exc).__name__}).",
                    iterations,
                    tool_history,
                    "error",
                    session,
                    request_id,
                )

            if response.reasoning:
                self._emit(
                    {
                        "type": "reasoning",
                        "content": response.reasoning,
                        "iteration": iterations,
                        "model": response.model,
                        "provider": response.provider,
                    }
                )
            self._emit(
                {
                    "type": "assistant",
                    "content": response.content,
                    "reasoning": response.reasoning,
                    "tool_calls": [
                        {"id": call.id, "name": call.name, "arguments": call.arguments}
                        for call in response.tool_calls
                    ],
                    "model": response.model,
                    "provider": response.provider,
                    "usage": response.usage,
                }
            )

            if not response.tool_calls:
                answer = (response.content or "").strip()
                if not answer:
                    return self._finish(
                        "Stopped: model returned no content and no tool calls.",
                        iterations,
                        tool_history,
                        "error",
                        session,
                        request_id,
                    )
                if session.design is not None:
                    session.update_plan("explain", "done")
                    self._emit({"type": "plan", "steps": session.plan})
                return self._finish(
                    answer, iterations, tool_history, "final", session, request_id
                )

            messages.append(
                ChatMessage(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls,
                )
            )
            for call in response.tool_calls:
                key = f"{call.name}:{json.dumps(call.arguments, sort_keys=True, default=str)}"
                repeat_count = repeat_count + 1 if key == last_key else 1
                last_key = key
                if repeat_count >= 3:
                    return self._finish(
                        f"Stopped: repeated {call.name} with identical arguments.",
                        iterations,
                        tool_history,
                        "loop",
                        session,
                        request_id,
                    )
                self._emit(
                    {
                        "type": "tool_call",
                        "tool": call.name,
                        "arguments": call.arguments,
                        "iteration": iterations,
                    }
                )
                before_decisions = len(session.decisions)
                start = time.perf_counter()
                success, output = self._execute(call.name, call.arguments, session)
                duration_ms = (time.perf_counter() - start) * 1000.0
                self._update_plan(session, call.name, output, success)
                for decision in session.decisions[before_decisions:]:
                    self._emit({"type": "decision", "decision": decision})
                self._emit({"type": "plan", "steps": session.plan})
                tool_history.append(
                    {
                        "tool": call.name,
                        "input": call.arguments,
                        "output": output,
                        "success": success,
                    }
                )
                self.logger.log_tool(
                    request_id=request_id,
                    tool=call.name,
                    arguments=call.arguments,
                    output=output,
                    success=success,
                    duration_ms=duration_ms,
                    provider=response.provider,
                    model=response.model,
                    iteration=iterations,
                )
                self._emit(
                    {
                        "type": "tool_result",
                        "tool": call.name,
                        "success": success,
                        "output": output,
                        "duration_ms": round(duration_ms, 1),
                    }
                )
                messages.append(
                    ChatMessage(
                        role="tool",
                        content=json.dumps(output, default=str),
                        tool_call_id=call.id,
                        name=call.name,
                    )
                )

        return self._finish(
            f"Stopped: reached the {self.max_iterations}-tool-call limit.",
            iterations,
            tool_history,
            "max_iterations",
            session,
            request_id,
        )

    def _update_plan(
        self, session: AgentSession, tool: str, output: dict, success: bool
    ) -> None:
        if tool == "set_fixtures":
            session.ensure_plan(reset=True)
            return
        step = TOOL_STEP.get(tool)
        if step is None:
            return
        if not success:
            session.update_plan(step, "error")
            return
        session.update_plan(step, "done")
        if tool == "validate_design":
            counts = output.get("counts") or {}
            if counts.get("ERROR", 0) == 0:
                if output.get("fixes"):
                    session.update_plan("fix", "pending")
                elif session.applied_fixes:
                    session.update_plan("fix", "done")
                else:
                    session.update_plan("fix", "skipped")
            else:
                session.update_plan("fix", "pending")
        elif tool == "list_layout_options":
            session.update_plan("select", "pending")
            session.update_plan("route", "pending")
            session.update_plan("validate", "pending")
            session.update_plan("fix", "pending")
            session.update_plan("explain", "pending")

    def _execute(self, name: str, arguments: dict, session: AgentSession) -> tuple[bool, dict]:
        tool = TOOLS.get(name)
        if tool is None:
            return False, {"error": f"Unknown tool {name!r}."}
        try:
            return True, tool.run(arguments or {}, session)
        except ToolError as exc:
            return False, {"error": str(exc)}
        except Exception as exc:
            return False, {"error": f"Internal tool error ({type(exc).__name__})."}

    def _finish(
        self,
        answer: str,
        iterations: int,
        tool_history: list[dict],
        reason: str,
        session: AgentSession,
        request_id: str,
    ) -> AgentResult:
        if session.design is not None and session.plan:
            for step in session.plan:
                if step.get("id") == "explain" and step.get("status") == "pending":
                    step["status"] = "done"
            self._emit({"type": "plan", "steps": session.plan})
        self._emit(
            {
                "type": "final",
                "content": answer,
                "stopped_reason": reason,
                "iterations": iterations,
            }
        )
        self.logger.log_event(
            request_id=request_id,
            kind="final",
            payload={"answer": answer, "stopped_reason": reason},
            provider=self.provider.name,
            model=self.provider.model,
        )
        return AgentResult(answer, iterations, tool_history, reason, session)

    def _emit(self, event: dict) -> None:
        if self.on_event is None:
            return
        try:
            self.on_event(event)
        except Exception:
            pass
