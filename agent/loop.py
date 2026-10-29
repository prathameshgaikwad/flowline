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
        request_id = request_id or uuid.uuid4().hex[:8]
        history: list[dict] = []
        messages = [
            ChatMessage(role="system", content=SYSTEM_PROMPT + "\n\n" + build_context(session)),
            ChatMessage(role="user", content=request),
        ]
        self._emit({"type": "status", "message": "Agent started.", "request_id": request_id})

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
                    history,
                    "error",
                    session,
                    request_id,
                )
            except Exception as exc:
                return self._finish(
                    f"Stopped: unexpected provider error ({type(exc).__name__}).",
                    iterations,
                    history,
                    "error",
                    session,
                    request_id,
                )

            self._emit(
                {
                    "type": "assistant",
                    "content": response.content,
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
                        history,
                        "error",
                        session,
                        request_id,
                    )
                return self._finish(answer, iterations, history, "final", session, request_id)

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
                        history,
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
                start = time.perf_counter()
                success, output = self._execute(call.name, call.arguments, session)
                duration_ms = (time.perf_counter() - start) * 1000.0
                history.append(
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
            history,
            "max_iterations",
            session,
            request_id,
        )

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
        history: list[dict],
        reason: str,
        session: AgentSession,
        request_id: str,
    ) -> AgentResult:
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
        return AgentResult(answer, iterations, history, reason, session)

    def _emit(self, event: dict) -> None:
        if self.on_event is None:
            return
        try:
            self.on_event(event)
        except Exception:
            pass
