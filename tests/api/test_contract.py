from api.contract import ModelResponse, TextPart, ToolCallPart


def test_response_exposes_text_and_tool_calls():
    response = ModelResponse(
        content=[
            TextPart(text="hello"),
            ToolCallPart(id="call-1", name="test_tool", input={"value": 1}),
        ],
        stop_reason="tool_use",
    )

    assert response.text == "hello"
    assert response.tool_calls[0].id == "call-1"
