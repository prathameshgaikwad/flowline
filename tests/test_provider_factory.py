import pytest

from agent.providers.base import ConfigError
from agent.providers.factory import create_provider
from agent.providers.fake import FakeProvider
from agent.providers.meta import MetaProvider
from agent.providers.opencode import OpenCodeProvider
from agent.providers.openrouter import OpenRouterProvider


def test_meta_wins_when_both_keys_are_present():
    provider = create_provider(
        {"META_API_KEY": "meta-key", "OPENROUTER_API_KEY": "or-key"}
    )
    assert isinstance(provider, MetaProvider)
    assert provider.name == "meta"
    assert provider.model == "muse-spark-1.3"


def test_model_api_key_alias_selects_meta():
    provider = create_provider({"MODEL_API_KEY": "meta-key"})
    assert isinstance(provider, MetaProvider)


def test_opencode_key_selects_opencode():
    provider = create_provider({"OPENCODE_API_KEY": "oc-key"})
    assert isinstance(provider, OpenCodeProvider)
    assert provider.name == "opencode"
    assert provider.model == "muse-spark-1.3"


def test_opencode_go_plan_uses_go_defaults():
    provider = create_provider({"OPENCODE_API_KEY": "oc-key", "OPENCODE_PLAN": "go"})
    assert isinstance(provider, OpenCodeProvider)
    assert provider.base_url == "https://opencode.ai/inference/go/openai/v1"
    assert provider.model == "muse-spark-1.3-contributor"


def test_opencode_can_read_the_cli_auth_file(tmp_path):
    auth = tmp_path / "auth.json"
    auth.write_text(
        '{"opencode-go": {"type": "api", "key": "go-key"}}', encoding="utf-8"
    )
    provider = create_provider(
        {
            "OPENCODE_PLAN": "go",
            "OPENCODE_CLI_AUTH": "true",
            "OPENCODE_AUTH_FILE": str(auth),
            "OPENCODE_AUTH_PROVIDER": "opencode-go",
        }
    )
    assert isinstance(provider, OpenCodeProvider)
    assert provider.model == "muse-spark-1.3-contributor"


def test_meta_wins_over_opencode_and_openrouter():
    provider = create_provider(
        {
            "META_API_KEY": "meta-key",
            "OPENCODE_API_KEY": "oc-key",
            "OPENROUTER_API_KEY": "or-key",
        }
    )
    assert isinstance(provider, MetaProvider)


def test_opencode_wins_over_openrouter():
    provider = create_provider(
        {"OPENCODE_API_KEY": "oc-key", "OPENROUTER_API_KEY": "or-key"}
    )
    assert isinstance(provider, OpenCodeProvider)


def test_explicit_opencode_without_key_fails_fast():
    with pytest.raises(ConfigError, match="OPENCODE_API_KEY"):
        create_provider({"LLM_PROVIDER": "opencode"})


def test_openrouter_used_when_only_openrouter_key_is_present():
    provider = create_provider({"OPENROUTER_API_KEY": "or-key"})
    assert isinstance(provider, OpenRouterProvider)
    assert provider.name == "openrouter"


def test_no_keys_returns_fake_provider():
    provider = create_provider({})
    assert isinstance(provider, FakeProvider)
    assert provider.name == "fake"


def test_explicit_fake_wins_even_with_keys():
    provider = create_provider({"LLM_PROVIDER": "fake", "META_API_KEY": "meta-key"})
    assert isinstance(provider, FakeProvider)


def test_explicit_meta_without_key_fails_fast():
    with pytest.raises(ConfigError, match="META_API_KEY"):
        create_provider({"LLM_PROVIDER": "meta"})


def test_explicit_openrouter_without_key_fails_fast():
    with pytest.raises(ConfigError, match="OPENROUTER_API_KEY"):
        create_provider({"LLM_PROVIDER": "openrouter"})


def test_unknown_provider_fails():
    with pytest.raises(ConfigError, match="LLM_PROVIDER"):
        create_provider({"LLM_PROVIDER": "banana"})
