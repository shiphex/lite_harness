from types import SimpleNamespace

import api.gemini_api as gemini_api


def test_call_gemini_model_passes_request(monkeypatch):
    client_calls = []
    generate_calls = []
    fake_response = SimpleNamespace(text="fake response", function_calls=[])

    class FakeModels:
        def generate_content(self, **kwargs):
            generate_calls.append(kwargs)
            return fake_response

    class FakeClient:
        def __init__(self, **kwargs):
            client_calls.append(kwargs)
            self.models = FakeModels()

    monkeypatch.setattr(gemini_api.genai, "Client", FakeClient)

    response = gemini_api.call_gemini_model(
        model_info={
            "model_url": "http://localhost:8000",
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
        model_pattern="summary",
    )

    assert response.content[0].text == "fake response"
    assert response.stop_reason == "end_turn"
    assert client_calls == [{"api_key": "fake-key"}]
    assert generate_calls[0]["model"] == "test-model"
    assert generate_calls[0]["contents"][0].role == "user"
    assert generate_calls[0]["contents"][0].parts[0].text == "hello"
    assert generate_calls[0]["config"].max_output_tokens == 45
    assert generate_calls[0]["config"].system_instruction == "test system"
    assert generate_calls[0]["config"].tools[0].function_declarations[0].name == "test_tool"


def test_call_gemini_model_adapts_function_calls(monkeypatch):
    fake_response = SimpleNamespace(
        text="",
        function_calls=[
            SimpleNamespace(id="call-1", name="test_tool", args={"value": 3})
        ],
    )

    class FakeModels:
        def generate_content(self, **kwargs):
            return fake_response

    class FakeClient:
        def __init__(self, **kwargs):
            self.models = FakeModels()

    monkeypatch.setattr(gemini_api.genai, "Client", FakeClient)

    response = gemini_api.call_gemini_model(
        model_info={
            "model_url": "http://localhost:8000",
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

