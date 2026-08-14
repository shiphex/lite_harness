from event.interaction import (
    ApprovalRequest,
    ApprovalResponse,
    NonInteractiveInteraction,
)


def test_approval_models_store_request_and_response_data():
    request = ApprovalRequest(
        tool_call_id="call-1",
        tool_name="powershell",
        arguments={"command": "Remove-Item test.py"},
        reason="dangerous command",
    )

    assert request.tool_call_id == "call-1"
    assert request.tool_name == "powershell"
    assert request.arguments == {"command": "Remove-Item test.py"}
    assert request.reason == "dangerous command"
    assert ApprovalResponse(approved=True).approved is True


def test_non_interactive_interaction_denies_approval_by_default():
    request = ApprovalRequest("call-1", "demo_tool", {}, "confirm")

    response = NonInteractiveInteraction().request_approval(request)

    assert response.approved is False

