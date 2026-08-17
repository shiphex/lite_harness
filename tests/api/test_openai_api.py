from types import SimpleNamespace

import api.old_api.openai_api as openai_api


def test_call_openai_model_passes_request(monkeypatch):
    client_calls = []
    create_calls = []
    fake_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="fake response", tool_calls=[]),
                finish_reason="stop",
            )
        ]
    )

    class FakeCompletions:
        def create(self, **kwargs):
            create_calls.append(kwargs)
            return fake_response

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            client_calls.append(kwargs)
            self.chat = FakeChat()

    monkeypatch.setattr(openai_api, "OpenAI", FakeOpenAI)

    response = openai_api.call_openai_model(
        model_info={
            "model_url": "http://fake-api.example",
            "api_key": "fake-key",
            "model_name": "test-model",
        },
        content_info={
            "MAIN_OUTPUT_TOKENS": 123,
            "SUMMARY_OUTPUT_TOKENS": 45,
        },
        messages=[{"role": "user", "content": "hello"}],
        system_prompt="test system",
        tools=[
            {
                "name": "test_tool",
                "description": "test description",
                "input_schema": {"type": "object", "properties": {}},
            }
        ],
    )

    assert response.content[0].text == "fake response"
    assert response.stop_reason == "end_turn"
    assert client_calls == [
        {"base_url": "http://fake-api.example", "api_key": "fake-key"}
    ]
    assert create_calls[0]["model"] == "test-model"
    assert create_calls[0]["max_tokens"] == 123
    assert create_calls[0]["messages"] == [
        {"role": "system", "content": "test system"},
        {"role": "user", "content": "hello"},
    ]
    assert create_calls[0]["tools"][0]["function"]["name"] == "test_tool"


def test_call_openai_model_adapts_tool_calls(monkeypatch):
    fake_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=None,
                    tool_calls=[
                        SimpleNamespace(
                            id="call-1",
                            function=SimpleNamespace(
                                name="test_tool",
                                arguments='{"value": 3}',
                            ),
                        )
                    ],
                ),
                finish_reason="tool_calls",
            )
        ]
    )

    class FakeCompletions:
        def create(self, **kwargs):
            return fake_response

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    monkeypatch.setattr(openai_api, "OpenAI", FakeOpenAI)

    response = openai_api.call_openai_model(
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
    )

    assert response.stop_reason == "tool_use"
    assert response.content[0].type == "tool_use"
    assert response.content[0].id == "call-1"
    assert response.content[0].name == "test_tool"
    assert response.content[0].input == {"value": 3}

