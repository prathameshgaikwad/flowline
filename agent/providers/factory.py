from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path

from agent.providers.base import ConfigError, LLMProvider
from agent.providers.fake import FakeProvider
from agent.providers.meta import (
    DEFAULT_BASE_URL as META_DEFAULT_BASE_URL,
)
from agent.providers.meta import (
    DEFAULT_MODEL as META_DEFAULT_MODEL,
)
from agent.providers.meta import (
    MetaProvider,
)
from agent.providers.opencode import (
    OpenCodeProvider,
)
from agent.providers.openrouter import (
    DEFAULT_BASE_URL as OPENROUTER_DEFAULT_BASE_URL,
)
from agent.providers.openrouter import (
    DEFAULT_MODEL as OPENROUTER_DEFAULT_MODEL,
)
from agent.providers.openrouter import (
    OpenRouterProvider,
)

VALID_PROVIDERS = {"auto", "meta", "opencode", "openrouter", "fake"}


def create_provider(env: Mapping[str, str] | None = None) -> LLMProvider:
    values = os.environ if env is None else env
    requested = (values.get("LLM_PROVIDER") or "auto").strip().lower()
    if requested not in VALID_PROVIDERS:
        raise ConfigError(
            f"Unknown LLM_PROVIDER={requested!r}; use auto, meta, opencode, openrouter, or fake."
        )

    meta_key = values.get("META_API_KEY") or values.get("MODEL_API_KEY") or ""
    opencode_plan = (values.get("OPENCODE_PLAN") or "console").strip().lower()
    if opencode_plan not in {"console", "go"}:
        raise ConfigError("OPENCODE_PLAN must be 'console' or 'go'.")
    opencode_key = _opencode_key(values, opencode_plan)
    openrouter_key = values.get("OPENROUTER_API_KEY") or ""

    if requested == "auto":
        if meta_key:
            requested = "meta"
        elif opencode_key:
            requested = "opencode"
        elif openrouter_key:
            requested = "openrouter"
        else:
            requested = "fake"

    if requested == "meta":
        if not meta_key:
            raise ConfigError("META_API_KEY (or MODEL_API_KEY) is required for the Meta provider.")
        return MetaProvider(
            api_key=meta_key,
            model=values.get("META_MODEL") or META_DEFAULT_MODEL,
            base_url=values.get("META_BASE_URL") or META_DEFAULT_BASE_URL,
            timeout_s=_float_env(values, "LLM_TIMEOUT_SECONDS", 120.0),
            max_tokens=_int_env(values, "LLM_MAX_TOKENS", 4096),
        )

    if requested == "opencode":
        if not opencode_key:
            raise ConfigError(
                "OPENCODE_API_KEY (or OPENCODE_CLI_AUTH=true) is required for the "
                "OpenCode provider."
            )
        return OpenCodeProvider(
            api_key=opencode_key,
            model=values.get("OPENCODE_MODEL") or None,
            base_url=values.get("OPENCODE_BASE_URL") or None,
            plan=opencode_plan,
            timeout_s=_float_env(values, "LLM_TIMEOUT_SECONDS", 120.0),
            max_tokens=_int_env(values, "LLM_MAX_TOKENS", 4096),
        )

    if requested == "openrouter":
        if not openrouter_key:
            raise ConfigError("OPENROUTER_API_KEY is required for the OpenRouter provider.")
        return OpenRouterProvider(
            api_key=openrouter_key,
            model=values.get("OPENROUTER_MODEL") or OPENROUTER_DEFAULT_MODEL,
            base_url=values.get("OPENROUTER_BASE_URL") or OPENROUTER_DEFAULT_BASE_URL,
            timeout_s=_float_env(values, "LLM_TIMEOUT_SECONDS", 120.0),
            max_tokens=_int_env(values, "LLM_MAX_TOKENS", 4096),
        )

    return FakeProvider()


def _opencode_key(values: Mapping[str, str], plan: str) -> str:
    key = values.get("OPENCODE_API_KEY") or ""
    if key:
        return key
    if (values.get("OPENCODE_CLI_AUTH") or "").lower() not in ("1", "true", "yes"):
        return ""
    path = Path(
        os.path.expanduser(
            values.get("OPENCODE_AUTH_FILE")
            or (Path.home() / ".local/share/opencode/auth.json")
        )
    )
    provider = values.get("OPENCODE_AUTH_PROVIDER") or (
        "opencode-go" if plan == "go" else "opencode"
    )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    entry = data.get(provider) or {}
    return str(entry.get("key") or "")


def _float_env(values: Mapping[str, str], key: str, default: float) -> float:
    try:
        return float(values.get(key) or default)
    except (TypeError, ValueError):
        return default


def _int_env(values: Mapping[str, str], key: str, default: int) -> int:
    try:
        return int(values.get(key) or default)
    except (TypeError, ValueError):
        return default
