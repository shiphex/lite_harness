import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api import adapter_factory


class FakeAdapter:
    @classmethod
    def from_model_config(cls, model_config):
        return cls()


@pytest.mark.parametrize(
    ("config_key", "provider", "adapter_name"),
    [
        ("api", "anthropic", "AnthropicAdapter"),
        ("API", "OpenAI", "OpenAIAdapter"),
        ("api", "GEMINI", "GeminiAdapter"),
        ("API", "LangChain", "LangChainAdapter"),
    ],
)
def test_create_adapter_selects_provider(monkeypatch, config_key, provider, adapter_name):
    monkeypatch.setattr(adapter_factory, adapter_name, FakeAdapter)

    result = adapter_factory.create_adapter({config_key: provider})

    assert isinstance(result, FakeAdapter)


def test_create_adapter_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unsupported model API"):
        adapter_factory.create_adapter({"api": "unknown"})
