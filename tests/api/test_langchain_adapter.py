from types import SimpleNamespace

from api.contract import ModelRequest
from api.langchain_adapter import LangChainAdapter


def test_langchain_adapter_wraps_legacy_response(monkeypatch):
    raw_response = SimpleNamespace(
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

    monkeypatch.setattr(
        "api.langchain_adapter.call_langchain_model",
        lambda **kwargs: raw_response,
    )

    adapter = LangChainAdapter.from_model_config(
        {
            "model_name": "test-model",
            "model_url": "http://localhost:8000",
            "api_key": "no-key",
        }
    )
    response = adapter.complete(
        ModelRequest(model="test-model", messages=[], max_tokens=123)
    )

    assert response.text == "hello"
    assert response.tool_calls[0].name == "test_tool"
    assert response.stop_reason == "tool_use"
