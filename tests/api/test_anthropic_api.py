from types import SimpleNamespace

import api.old_api.anthropic_api as anthropic_api


def test_call_anthropic_model(monkeypatch):
    anthropic_calls = []
    create_calls = []
    fake_response = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="fake response"),
        ],
    )

    class FakeMessages:
        def create(self, **kwargs):
            create_calls.append(kwargs)
            return fake_response

    class FakeAnthropic:
        def __init__(self, **kwargs):
            anthropic_calls.append(kwargs)
            self.messages = FakeMessages()

    monkeypatch.setattr(anthropic_api, "Anthropic", FakeAnthropic)

    model_info = {
        "api": "anthropic",
        "model_url": "http://fake-api.example",
        "api_key": "fake-key",
        "model_name": "test-model",
    }
    content_info = {
        "MAIN_OUTPUT_TOKENS": 123,
        "SUMMARY_OUTPUT_TOKENS": 45,
    }
    messages = [{"role": "user", "content": "hello"}]
    tools = [{"name": "test_tool"}]

    response = anthropic_api.call_anthropic_model(
        model_info=model_info,
        content_info=content_info,
        messages=messages,
        system_prompt="test system",
        tools=tools,
    )

    assert response is fake_response
    assert anthropic_calls == [
        {
            "base_url": "http://fake-api.example",
            "api_key": "fake-key",
        }
    ]
    assert create_calls == [
        {
            "model": "test-model",
            "messages": messages,
            "system": "test system",
            "tools": tools,
            "max_tokens": 123,
        }
    ]


def test_call_anthropic_model_uses_summary_tokens(monkeypatch):
    create_calls = []
    fake_response = SimpleNamespace(content=[])

    class FakeMessages:
        def create(self, **kwargs):
            create_calls.append(kwargs)
            return fake_response

    class FakeAnthropic:
        def __init__(self, **kwargs):
            self.messages = FakeMessages()

    monkeypatch.setattr(anthropic_api, "Anthropic", FakeAnthropic)

    response = anthropic_api.call_anthropic_model(
        model_info={
            "model_url": "http://fake-api.example",
            "api_key": "fake-key",
            "model_name": "test-model",
        },
        content_info={
            "MAIN_OUTPUT_TOKENS": 123,
            "SUMMARY_OUTPUT_TOKENS": 45,
        },
        messages=[],
        model_pattern="summary",
    )

    assert response is fake_response
    assert create_calls[0]["max_tokens"] == 45
