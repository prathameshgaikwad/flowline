import io
import json
import urllib.error

import pytest

from agent.providers.base import ChatMessage, LLMError
from agent.providers.chat_completions import ChatCompletionsProvider
from agent.providers.meta import MetaProvider
from agent.providers.openrouter import OpenRouterProvider


class FakeHttpResponse:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _response_body(content="hello", tool_calls=None):
    message = {"role": "assistant", "content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    return {"model": "muse-spark-1.3", "choices": [{"message": message}]}


def test_meta_defaults():
    provider = MetaProvider(api_key="k")
    assert provider.name == "meta"
    assert provider.model == "muse-spark-1.3"
    assert provider.base_url == "https://api.meta.ai/v1"


def test_openrouter_defaults():
    provider = OpenRouterProvider(api_key="k")
    assert provider.name == "openrouter"
    assert provider.base_url == "https://openrouter.ai/api/v1"


def test_payload_uses_openai_tool_format(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout=0):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeHttpResponse(_response_body())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = ChatCompletionsProvider(
        base_url="https://example.test/v1", api_key="secret", model="m", name="test"
    )
    tools = [{"type": "function", "function": {"name": "inspect_plan", "parameters": {}}}]
    result = provider.chat([ChatMessage(role="user", content="hi")], tools=tools)

    assert result.content == "hello"
    assert result.provider == "test"
    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["body"]["model"] == "m"
    assert captured["body"]["tools"] == tools
    assert captured["body"]["messages"][0] == {"role": "user", "content": "hi"}


def test_parses_tool_calls(monkeypatch):
    calls = [
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "inspect_plan", "arguments": "{\"room_id\": \"R1\"}"},
        }
    ]

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout=0: FakeHttpResponse(_response_body(None, calls)),
    )
    provider = MetaProvider(api_key="k")
    result = provider.chat([ChatMessage(role="user", content="hi")])
    assert result.tool_calls[0].name == "inspect_plan"
    assert result.tool_calls[0].arguments == {"room_id": "R1"}
    assert result.content is None


def test_http_error_is_wrapped(monkeypatch):
    def raise_http_error(request, timeout=0):
        raise urllib.error.HTTPError(
            request.full_url, 401, "Unauthorized", {}, io.BytesIO(b"bad key")
        )

    monkeypatch.setattr("urllib.request.urlopen", raise_http_error)
    provider = MetaProvider(api_key="k")
    with pytest.raises(LLMError, match="401"):
        provider.chat([ChatMessage(role="user", content="hi")])


def test_retries_on_rate_limit(monkeypatch):
    attempts = {"count": 0}

    def flaky(request, timeout=0):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise urllib.error.HTTPError(
                request.full_url, 429, "Too Many Requests", {}, io.BytesIO(b"slow down")
            )
        return FakeHttpResponse(_response_body("ok"))

    monkeypatch.setattr("urllib.request.urlopen", flaky)
    provider = ChatCompletionsProvider(
        base_url="https://example.test/v1",
        api_key="k",
        model="m",
        name="test",
        retry_delays=(0, 0),
    )
    assert provider.chat([ChatMessage(role="user", content="hi")]).content == "ok"
    assert attempts["count"] == 2


def test_malformed_tool_arguments_raise(monkeypatch):
    calls = [
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "inspect_plan", "arguments": "not-json"},
        }
    ]
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout=0: FakeHttpResponse(_response_body(None, calls)),
    )
    provider = MetaProvider(api_key="k")
    with pytest.raises(LLMError, match="malformed tool call"):
        provider.chat([ChatMessage(role="user", content="hi")])
