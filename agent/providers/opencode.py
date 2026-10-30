from __future__ import annotations

from uuid import uuid4

from agent.providers.chat_completions import ChatCompletionsProvider

DEFAULT_BASE_URL = "https://opencode.ai/inference/openai/v1"
DEFAULT_GO_BASE_URL = "https://opencode.ai/inference/go/openai/v1"
DEFAULT_MODEL = "muse-spark-1.3"
DEFAULT_GO_MODEL = "muse-spark-1.3-contributor"


class OpenCodeProvider(ChatCompletionsProvider):
    """OpenCode Console (pay-as-you-go) or OpenCode Go (subscription).

    Console and Go share one credential in OpenCode's CLI, but different
    endpoints and billing lanes. Go requires the x-opencode-session header.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str | None = None,
        base_url: str | None = None,
        plan: str = "console",
        session_id: str | None = None,
        timeout_s: float = 120.0,
        max_tokens: int = 4096,
    ) -> None:
        plan = (plan or "console").strip().lower()
        if plan not in {"console", "go"}:
            raise ValueError("OPENCODE_PLAN must be 'console' or 'go'.")
        self.plan = plan
        resolved_base = base_url or (
            DEFAULT_GO_BASE_URL if plan == "go" else DEFAULT_BASE_URL
        )
        resolved_model = model or (
            DEFAULT_GO_MODEL if plan == "go" else DEFAULT_MODEL
        )
        super().__init__(
            base_url=resolved_base,
            api_key=api_key,
            model=resolved_model,
            name="opencode",
            headers={
                "Accept": "application/json",
                "x-opencode-session": session_id or uuid4().hex,
            },
            timeout_s=timeout_s,
            max_tokens=max_tokens,
        )
