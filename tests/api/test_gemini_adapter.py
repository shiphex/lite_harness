from types import SimpleNamespace

from api.contract import ModelRequest
from api.gemini_adapter import GeminiAdapter


def test_gemini_adapter_converts_request():
    adapter = GeminiAdapter(SimpleNamespace())
    request = ModelRequest(
        model="test-model",
        messages=[{"role": "user", "content": "hello"}],
        system_prompt="system",
        tools=[{"name": "test_tool"}],
        max_tokens=123,
    )

    payload = adapter.encode_request(request)

    assert payload["model"] == "test-model"
    assert payload["contents"][0].role == "user"
    assert payload["contents"][0].parts[0].text == "hello"
    assert payload["config"].max_output_tokens == 123
    assert payload["config"].system_instruction == "system"


def test_gemini_adapter_decodes_function_call():
    response = SimpleNamespace(
        text="hello",
        function_calls=[
            SimpleNamespace(id="call-1", name="test_tool", args={"value": 1})
        ],
    )
    result = GeminiAdapter(SimpleNamespace()).decode_response(response)

    assert result.text == "hello"
    assert result.tool_calls[0].id == "call-1"
    assert result.tool_calls[0].input == {"value": 1}
    assert result.stop_reason == "tool_use"
