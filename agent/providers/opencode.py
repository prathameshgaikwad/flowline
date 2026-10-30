from __future__ import annotations

from agent.providers.chat_completions import ChatCompletionsProvider

DEFAULT_BASE_URL = "https://opencode.ai/inference/openai/v1"
DEFAULT_MODEL = "muse-spark-1.3"


class OpenCodeProvider(ChatCompletionsProvider):
    """OpenCode Console / OpenCode Go inference gateway.

    The gateway is OpenAI-compatible and exposes Meta Muse Spark 1.3.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        timeout_s: float = 120.0,
        max_tokens: int = 4096,
    ) -> None:
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            model=model,
            name="opencode",
            headers={"Accept": "application/json"},
            timeout_s=timeout_s,
            max_tokens=max_tokens,
        )
