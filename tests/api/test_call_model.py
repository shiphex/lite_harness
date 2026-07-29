import importlib
from types import SimpleNamespace


def test_call_model(monkeypatch):
    call_model_module = importlib.import_module("api.call_model")
    calls = []
    fake_response = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="fake response"),
        ],
    )
    model_config = {
        "api": "anthropic",
        "model_url": "http://fake-api.example",
        "api_key": "fake-key",
        "model_name": "test-model",
    }
    content_info = {
        "MAIN_OUTPUT_TOKENS": 5120,
        "SUMMARY_OUTPUT_TOKENS": 2048,
    }

    def fake_call_anthropic_model(
        model_info,
        content_info,
        messages,
        system_prompt,
        tools,
        model_pattern,
    ):
        calls.append(
            {
                "model_info": model_info,
                "content_info": content_info,
                "messages": messages,
                "system_prompt": system_prompt,
                "tools": tools,
                "model_pattern": model_pattern,
            }
        )
        return fake_response

    monkeypatch.setattr(
        call_model_module,
        "get_model_config",
        lambda: (model_config, content_info),
    )
    monkeypatch.setattr(
        call_model_module,
        "call_anthropic_model",
        fake_call_anthropic_model,
    )

    messages = [{"role": "user", "content": "hello"}]
    tools = [{"name": "test_tool"}]
    response = call_model_module.call_model(
        messages=messages,
        system_prompt="test system",
        tools=tools,
    )

    assert response is fake_response
    assert calls == [
        {
            "model_info": model_config,
            "content_info": content_info,
            "messages": messages,
            "system_prompt": "test system",
            "tools": tools,
            "model_pattern": "default",
        }
    ]


def test_call_model_passes_summary_model_pattern(monkeypatch):
    call_model_module = importlib.import_module("api.call_model")
    calls = []
    fake_response = SimpleNamespace(content=[])
    model_config = {
        "api": "anthropic",
        "model_url": "http://fake-api.example",
        "api_key": "fake-key",
        "model_name": "test-model",
    }
    content_info = {
        "MAIN_OUTPUT_TOKENS": 5120,
        "SUMMARY_OUTPUT_TOKENS": 2048,
    }

    def fake_call_anthropic_model(**kwargs):
        calls.append(kwargs)
        return fake_response

    monkeypatch.setattr(
        call_model_module,
        "get_model_config",
        lambda: (model_config, content_info),
    )
    monkeypatch.setattr(
        call_model_module,
        "call_anthropic_model",
        fake_call_anthropic_model,
    )

    response = call_model_module.call_model(
        messages=[],
        system_prompt="summary system",
        tools=[],
        model_pattern="summary",
    )

    assert response is fake_response
    assert calls[0]["model_pattern"] == "summary"


def test_get_model_config_uses_current_config():
    call_model_module = importlib.import_module("api.call_model")

    try:
        call_model_module.config.configure([
            "--model_name",
            "configured-model",
            "--api_key",
            "configured-key",
        ])
        model_config, content_info = call_model_module.get_model_config()

        assert model_config["model_name"] == "configured-model"
        assert model_config["api_key"] == "configured-key"
        assert content_info["MAIN_OUTPUT_TOKENS"] == 5120
    finally:
        call_model_module.config.configure([])


def test_call_model_routes_openai(monkeypatch):
    call_model_module = importlib.import_module("api.call_model")
    calls = []
    fake_response = SimpleNamespace(content=[])
    model_config = {
        "api": "openai",
        "model_url": "http://fake-api.example",
        "api_key": "fake-key",
        "model_name": "test-model",
    }
    content_info = {
        "MAIN_OUTPUT_TOKENS": 5120,
        "SUMMARY_OUTPUT_TOKENS": 2048,
    }

    def fake_call_openai_model(**kwargs):
        calls.append(kwargs)
        return fake_response

    monkeypatch.setattr(
        call_model_module,
        "get_model_config",
        lambda: (model_config, content_info),
    )
    monkeypatch.setattr(
        call_model_module,
        "call_openai_model",
        fake_call_openai_model,
    )

    response = call_model_module.call_model(
        messages=[{"role": "user", "content": "hello"}],
        system_prompt="test system",
        tools=[{"name": "test_tool"}],
        model_pattern="summary",
    )

    assert response is fake_response
    assert calls == [
        {
            "model_info": model_config,
            "content_info": content_info,
            "messages": [{"role": "user", "content": "hello"}],
            "system_prompt": "test system",
            "tools": [{"name": "test_tool"}],
            "model_pattern": "summary",
        }
    ]


def test_call_model_routes_gemini(monkeypatch):
    call_model_module = importlib.import_module("api.call_model")
    calls = []
    fake_response = SimpleNamespace(content=[])
    model_config = {
        "api": "gemini",
        "model_url": "http://fake-api.example",
        "api_key": "fake-key",
        "model_name": "test-model",
    }
    content_info = {
        "MAIN_OUTPUT_TOKENS": 5120,
        "SUMMARY_OUTPUT_TOKENS": 2048,
    }

    def fake_call_gemini_model(**kwargs):
        calls.append(kwargs)
        return fake_response

    monkeypatch.setattr(
        call_model_module,
        "get_model_config",
        lambda: (model_config, content_info),
    )
    monkeypatch.setattr(
        call_model_module,
        "call_gemini_model",
        fake_call_gemini_model,
    )

    response = call_model_module.call_model(messages=[], system_prompt="", tools=[])

    assert response is fake_response
    assert calls[0]["model_info"] == model_config
    assert calls[0]["content_info"] == content_info
    assert calls[0]["model_pattern"] == "default"


def test_call_model_routes_langchain(monkeypatch):
    call_model_module = importlib.import_module("api.call_model")
    calls = []
    fake_response = SimpleNamespace(content=[])
    model_config = {
        "api": "langchain",
        "model_url": "http://fake-api.example",
        "api_key": "fake-key",
        "model_name": "test-model",
    }
    content_info = {
        "MAIN_OUTPUT_TOKENS": 5120,
        "SUMMARY_OUTPUT_TOKENS": 2048,
    }

    def fake_call_langchain_model(**kwargs):
        calls.append(kwargs)
        return fake_response

    monkeypatch.setattr(
        call_model_module,
        "get_model_config",
        lambda: (model_config, content_info),
    )
    monkeypatch.setattr(
        call_model_module,
        "call_langchain_model",
        fake_call_langchain_model,
    )

    response = call_model_module.call_model(messages=[], system_prompt="", tools=[])

    assert response is fake_response
    assert calls[0]["model_info"] == model_config
    assert calls[0]["content_info"] == content_info
    assert calls[0]["model_pattern"] == "default"
