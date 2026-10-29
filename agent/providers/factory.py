from __future__ import annotations

import os
from collections.abc import Mapping

from agent.providers.base import ConfigError, LLMProvider
from agent.providers.fake import FakeProvider
from agent.providers.meta import (
    DEFAULT_BASE_URL as META_DEFAULT_BASE_URL,
    DEFAULT_MODEL as META_DEFAULT_MODEL,
    MetaProvider,
)
from agent.providers.openrouter import (
    DEFAULT_BASE_URL as OPENROUTER_DEFAULT_BASE_URL,
    DEFAULT_MODEL as OPENROUTER_DEFAULT_MODEL,
    OpenRouterProvider,
)

VALID_PROVIDERS = {"auto", "meta", "openrouter", "fake"}


def create_provider(env: Mapping[str, str] | None = None) -> LLMProvider:
    values = os.environ if env is None else env
    requested = (values.get("LLM_PROVIDER") or "auto").strip().lower()
    if requested not in VALID_PROVIDERS:
        raise ConfigError(
            f"Unknown LLM_PROVIDER={requested!r}; use auto, meta, openrouter, or fake."
        )

    meta_key = values.get("META_API_KEY") or values.get("MODEL_API_KEY") or ""
    openrouter_key = values.get("OPENROUTER_API_KEY") or ""

    if requested == "auto":
        if meta_key:
            requested = "meta"
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
            timeout_s=_float_env(values, "LLM_TIMEOUT_SECONDS", 90.0),
            max_tokens=_int_env(values, "LLM_MAX_TOKENS", 4096),
        )

    if requested == "openrouter":
        if not openrouter_key:
            raise ConfigError("OPENROUTER_API_KEY is required for the OpenRouter provider.")
        return OpenRouterProvider(
            api_key=openrouter_key,
            model=values.get("OPENROUTER_MODEL") or OPENROUTER_DEFAULT_MODEL,
            base_url=values.get("OPENROUTER_BASE_URL") or OPENROUTER_DEFAULT_BASE_URL,
            timeout_s=_float_env(values, "LLM_TIMEOUT_SECONDS", 90.0),
            max_tokens=_int_env(values, "LLM_MAX_TOKENS", 4096),
        )

    return FakeProvider()


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
