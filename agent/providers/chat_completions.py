from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from agent.providers.base import ChatMessage, LLMError, LLMProvider, LLMResponse, ToolCall


class ChatCompletionsProvider(LLMProvider):
    """OpenAI-compatible Chat Completions client using only the standard library."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        name: str,
        headers: dict[str, str] | None = None,
        timeout_s: float = 120.0,
        max_tokens: int = 4096,
        retry_delays: tuple[float, ...] = (0.5, 1.0, 2.0),
    ) -> None:
        if not api_key:
            raise LLMError(f"{name}: API key is empty.")
        if not model:
            raise LLMError(f"{name}: model is empty.")
        if not base_url:
            raise LLMError(f"{name}: base URL is empty.")
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self.name = name
        self._headers = dict(headers or {})
        self._timeout_s = float(timeout_s)
        self._max_tokens = int(max_tokens)
        self._retry_delays = tuple(retry_delays)

    @property
    def model(self) -> str:
        return self._model

    def _payload(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None,
        tool_choice: str | dict | None,
    ) -> dict[str, Any]:
        wire: list[dict[str, Any]] = []
        for message in messages:
            item: dict[str, Any] = {"role": message.role}
            if message.content is not None:
                item["content"] = message.content
            if message.tool_calls:
                item["tool_calls"] = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(call.arguments),
                        },
                    }
                    for call in message.tool_calls
                ]
            if message.role == "tool":
                item["tool_call_id"] = message.tool_call_id
                if message.name:
                    item["name"] = message.name
            wire.append(item)

        body: dict[str, Any] = {
            "model": self._model,
            "messages": wire,
            "max_tokens": self._max_tokens,
        }
        if tools:
            body["tools"] = tools
        if tool_choice is not None:
            body["tool_choice"] = tool_choice
        return body

    def _request(self, body: dict[str, Any]) -> urllib.request.Request:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Flowline/0.1",
        }
        headers.update(self._headers)
        return urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        attempts = len(self._retry_delays) + 1
        for attempt in range(attempts):
            request = self._request(body)
            try:
                with urllib.request.urlopen(request, timeout=self._timeout_s) as response:
                    raw = response.read().decode("utf-8")
                try:
                    return json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise LLMError(f"{self.name} returned non-JSON: {raw[:220]!r}") from exc
            except urllib.error.HTTPError as exc:
                detail = _safe_read(exc)
                last_error = exc
                if exc.code in (429, 500, 502, 503, 504) and attempt < len(self._retry_delays):
                    time.sleep(self._retry_delays[attempt])
                    continue
                raise LLMError(f"{self.name} HTTP {exc.code}: {detail}") from exc
            except TimeoutError as exc:
                last_error = exc
                if attempt < len(self._retry_delays):
                    time.sleep(self._retry_delays[attempt])
                    continue
                raise LLMError(
                    f"{self.name} request timed out after {self._timeout_s}s."
                ) from exc
            except urllib.error.URLError as exc:
                last_error = exc
                if attempt < len(self._retry_delays):
                    time.sleep(self._retry_delays[attempt])
                    continue
                raise LLMError(f"{self.name} connection failed: {exc.reason}") from exc
        raise LLMError(f"{self.name} request failed: {last_error}")

    def _parse(self, body: dict[str, Any]) -> LLMResponse:
        try:
            message = body["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"{self.name} response has no choices[0].message.") from exc
        if not isinstance(message, dict):
            raise LLMError(f"{self.name} response message is not an object.")

        calls: list[ToolCall] = []
        for index, item in enumerate(message.get("tool_calls") or []):
            try:
                function = item["function"]
                raw_args = function.get("arguments", "{}") or "{}"
                arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                if not isinstance(arguments, dict):
                    raise ValueError("arguments must be a JSON object")
                calls.append(
                    ToolCall(
                        id=str(item.get("id") or f"call_{index}"),
                        name=str(function["name"]),
                        arguments=arguments,
                    )
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise LLMError(f"{self.name} returned a malformed tool call.") from exc

        return LLMResponse(
            content=message.get("content"),
            tool_calls=calls,
            model=str(body.get("model") or self._model),
            provider=self.name,
            usage=body.get("usage"),
        )

    def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
    ) -> LLMResponse:
        return self._parse(self._post(self._payload(messages, tools, tool_choice)))


def _safe_read(error: urllib.error.HTTPError) -> str:
    try:
        return error.read().decode("utf-8", "replace")[:500]
    except Exception:
        return str(error)
