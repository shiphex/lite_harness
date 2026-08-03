from types import SimpleNamespace

from api.anthropic_adapter import AnthropicAdapter
from api.contract import ModelRequest


def test_anthropic_adapter_encodes_request():
    adapter = AnthropicAdapter(SimpleNamespace())
    request = ModelRequest(
        model="test-model",
        messages=[{"role": "user", "content": "hello"}],
        system_prompt="system",
        tools=[{"name": "test_tool"}],
        max_tokens=123,
    )

    payload = adapter.encode_request(request)

    assert payload == {
        "model": "test-model",
        "messages": [{"role": "user", "content": "hello"}],
        "system": "system",
        "tools": [{"name": "test_tool"}],
        "max_tokens": 123,
    }


def test_anthropic_adapter_decodes_response():
    response = SimpleNamespace(
        id="response-1",
        stop_reason="tool_use",
        content=[
            SimpleNamespace(type="text", text="hello"),
            SimpleNamespace(
                type="tool_use",
                id="call-1",
                name="test_tool",
                input={"value": 1},
            ),
        ],
    )
    result = AnthropicAdapter(SimpleNamespace()).decode_response(response)

    assert result.text == "hello"
    assert result.tool_calls[0].input == {"value": 1}
    assert result.stop_reason == "tool_use"
