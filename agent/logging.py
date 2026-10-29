from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

SECRET_KEYS = ("key", "token", "secret", "password", "authorization")


class ActionLogger:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else None
        self._lock = threading.Lock()
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def log_tool(
        self,
        *,
        request_id: str,
        tool: str,
        arguments: dict[str, Any],
        output: dict[str, Any],
        success: bool,
        duration_ms: float,
        provider: str,
        model: str,
        iteration: int,
    ) -> None:
        self._write(
            {
                "ts": time.time(),
                "request_id": request_id,
                "kind": "tool",
                "iteration": iteration,
                "tool": tool,
                "arguments": _redact(arguments),
                "output": _summarize(output),
                "success": success,
                "duration_ms": round(duration_ms, 2),
                "provider": provider,
                "model": model,
            }
        )

    def log_event(
        self,
        *,
        request_id: str,
        kind: str,
        payload: dict[str, Any],
        provider: str,
        model: str,
    ) -> None:
        self._write(
            {
                "ts": time.time(),
                "request_id": request_id,
                "kind": kind,
                "payload": _redact(payload),
                "provider": provider,
                "model": model,
            }
        )

    def _write(self, item: dict[str, Any]) -> None:
        if self.path is None:
            return
        line = json.dumps(item, default=str)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("[redacted]" if any(token in key.lower() for token in SECRET_KEYS) else _redact(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _summarize(value: Any, limit: int = 800) -> Any:
    text = json.dumps(value, default=str)
    if len(text) <= limit:
        return value
    return text[:limit] + "...[truncated]"
