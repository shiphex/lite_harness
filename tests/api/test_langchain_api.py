from types import SimpleNamespace

import api.langchain_api as langchain_api


def test_call_langchain_model_passes_request(monkeypatch):
    init_calls = []
    bound_tools = []
    invoke_calls = []
    fake_response = SimpleNamespace(content="fake response", tool_calls=[])

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            init_calls.append(kwargs)

        def bind_tools(self, tools):
            bound_tools.append(tools)
            return self

        def invoke(self, messages):
            invoke_calls.append(messages)
            return fake_response

    monkeypatch.setattr(langchain_api, "ChatOpenAI", FakeChatOpenAI)

    response = langchain_api.call_langchain_model(
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
    assert init_calls == [
        {
            "model": "test-model",
            "api_key": "fake-key",
            "base_url": "http://fake-api.example",
            "max_completion_tokens": 123,
        }
    ]
    assert bound_tools[0][0]["name"] == "test_tool"
    assert invoke_calls[0][0].content == "test system"
    assert invoke_calls[0][1].content == "hello"


def test_call_langchain_model_adapts_tool_calls(monkeypatch):
    fake_response = SimpleNamespace(
        content="",
        tool_calls=[
            {
                "id": "call-1",
                "name": "test_tool",
                "args": {"value": 3},
                "type": "tool_call",
            }
        ],
    )

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            pass

        def invoke(self, messages):
            return fake_response

    monkeypatch.setattr(langchain_api, "ChatOpenAI", FakeChatOpenAI)

    response = langchain_api.call_langchain_model(
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

