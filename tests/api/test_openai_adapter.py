from types import SimpleNamespace

from api.contract import ModelRequest
from api.openai_adapter import OpenAIAdapter


def test_openai_adapter_converts_messages_and_tools():
    adapter = OpenAIAdapter(SimpleNamespace())
    request = ModelRequest(
        model="test-model",
        messages=[{"role": "user", "content": "hello"}],
        system_prompt="system",
        tools=[
            {
                "name": "test_tool",
                "description": "test description",
                "input_schema": {"type": "object", "properties": {}},
            }
        ],
        max_tokens=123,
    )

    payload = adapter.encode_request(request)

    assert payload["messages"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "hello"},
    ]
    assert payload["tools"][0]["function"]["name"] == "test_tool"
    assert payload["max_tokens"] == 123


def test_openai_adapter_decodes_tool_call():
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="tool_calls",
                message=SimpleNamespace(
                    content=None,
                    tool_calls=[
                        SimpleNamespace(
                            id="call-1",
                            function=SimpleNamespace(
                                name="test_tool",
                                arguments='{"value": 1}',
                            ),
                        )
                    ],
                ),
            )
        ]
    )
    result = OpenAIAdapter(SimpleNamespace()).decode_response(response)

    assert result.tool_calls[0].id == "call-1"
    assert result.tool_calls[0].input == {"value": 1}
    assert result.stop_reason == "tool_use"
