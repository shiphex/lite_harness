"""Factory for selecting a model adapter from a normalized model config."""

from typing import Any

from .anthropic_adapter import AnthropicAdapter
from .gemini_adapter import GeminiAdapter
from .langchain_adapter import LangChainAdapter
from .model_adapter import ModelAdapter
from .openai_adapter import OpenAIAdapter


def create_adapter(model_config: dict[str, Any]) -> ModelAdapter:
    """Create the provider adapter selected by ``api`` or ``API``."""
    provider = str(
        model_config.get("api", model_config.get("API", ""))
    ).lower()
    adapters = {
        "anthropic": AnthropicAdapter,
        "openai": OpenAIAdapter,
        "gemini": GeminiAdapter,
        "langchain": LangChainAdapter,
    }

    try:
        adapter_type = adapters[provider]
    except KeyError as exc:
        raise ValueError(f"Unsupported model API: {provider or '<missing>'}") from exc

    return adapter_type.from_model_config(model_config)
