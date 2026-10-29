from __future__ import annotations

from agent.providers.chat_completions import ChatCompletionsProvider

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"


class OpenRouterProvider(ChatCompletionsProvider):
    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        timeout_s: float = 90.0,
        max_tokens: int = 4096,
        app_title: str = "Flowline",
    ) -> None:
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            model=model,
            name="openrouter",
            headers={
                "HTTP-Referer": "https://github.com/prathameshgaikwad/flowline",
                "X-Title": app_title,
            },
            timeout_s=timeout_s,
            max_tokens=max_tokens,
        )
