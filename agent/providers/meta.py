from __future__ import annotations

from agent.providers.chat_completions import ChatCompletionsProvider

DEFAULT_BASE_URL = "https://api.meta.ai/v1"
DEFAULT_MODEL = "muse-spark-1.3"


class MetaProvider(ChatCompletionsProvider):
    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        timeout_s: float = 90.0,
        max_tokens: int = 4096,
    ) -> None:
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            model=model,
            name="meta",
            timeout_s=timeout_s,
            max_tokens=max_tokens,
        )
