import importlib
import sys
from pathlib import Path

import pytest


from config import (
    Config,
    configure,
    get_current_args,
    get_system_prompt_config,
    parse_args,
    set_other_prompt,
    update_config,
)


def test_parse_args_defaults():
    """未传入参数时，应返回默认配置。"""

    result = parse_args([])

    assert result == {
        "chars_per_token": 1.0,
        "ctx_tokens": 20480,
        "max_tokens": 2048,
        "api": "anthropic",
        "model_url": "http://localhost:8000",
        "api_key": "no-key",
        "model_name": "claude-fable-5",
    }


def test_parse_args_accepts_supported_apis():
    for api in ("anthropic", "openai", "gemini", "langchain"):
        result = parse_args(["--api", api])

        assert result["api"] == api


def test_parse_args_rejects_unsupported_api():
    with pytest.raises(SystemExit):
        parse_args(["--api", "unsupported"])


def test_config_model_config_uses_api_key():
    result = Config(**parse_args([])).get_model_config()

    assert result["api_key"] == "no-key"


def test_config_content_length_includes_mini_output_tokens():
    result = Config(**parse_args([])).get_content_length()

    assert result["MINI_OUTPUT_TOKENS"] == 204


def test_configure_defaults_are_used_by_config():
    configure([])

    result = Config().get_model_config()

    assert result["api_key"] == "no-key"
    assert result["model_name"] == "claude-fable-5"


def test_configure_command_line_args_are_used_by_config():
    configure(["--model_name", "custom-model", "--api_key", "custom-key"])

    result = Config().get_model_config()

    assert result["api_key"] == "custom-key"
    assert result["model_name"] == "custom-model"


def test_update_config_changes_future_config_instances():
    configure([])

    update_config(model_name="runtime-model")

    assert Config().get_model_config()["model_name"] == "runtime-model"


def test_get_current_args_returns_copy():
    configure([])
    current_args = get_current_args()

    current_args["model_name"] = "mutated-outside"

    assert Config().get_model_config()["model_name"] == "claude-fable-5"


def test_set_other_prompt_adds_prompt_to_system_prompt():
    set_other_prompt("SKILL_PROMPT", "skill prompt text")

    assert "skill prompt text" in Config().get_system_prompt()


def test_set_other_prompt_overwrites_existing_prompt():
    set_other_prompt("SKILL_PROMPT", "old prompt")
    set_other_prompt("SKILL_PROMPT", "new prompt")

    system_prompt = Config().get_system_prompt()

    assert "new prompt" in system_prompt
    assert "old prompt" not in system_prompt
    assert get_system_prompt_config()["SKILL_PROMPT"] == "new prompt"


def test_import_config_does_not_parse_pytest_args(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["pytest", "--collect-only"])
    monkeypatch.delitem(sys.modules, "config.config", raising=False)
    monkeypatch.delitem(sys.modules, "config", raising=False)

    imported_config = importlib.import_module("config")

    assert imported_config.Config().get_path_config("project_path") == Path.cwd()
