from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import config  # noqa: E402,F401  (loads .env)
from agent.providers.base import ChatMessage, ConfigError, LLMError  # noqa: E402
from agent.providers.factory import create_provider  # noqa: E402


def main() -> int:
    try:
        provider = create_provider()
    except ConfigError as exc:
        print(f"BLOCKED: {exc}")
        return 2

    print(f"provider={provider.name} model={provider.model}")
    if provider.name == "fake":
        print("No Meta or OpenRouter key found; the fake provider will run the demo.")
        return 0

    try:
        response = provider.chat(
            [ChatMessage(role="user", content="Reply with the single word: ready")]
        )
    except LLMError as exc:
        print(f"FAILED: {exc}")
        return 1
    print(f"response={((response.content or '').strip())[:200]!r}")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
