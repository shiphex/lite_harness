import pytest

from cli.cli_interaction import CliInteraction
from event.interaction import ApprovalRequest


def request():
    return ApprovalRequest(
        tool_call_id="call-1",
        tool_name="powershell",
        arguments={"command": "Remove-Item test.py"},
        reason="dangerous command",
    )


@pytest.mark.parametrize("choice", ["y", "yes", "Y", "YES"])
def test_cli_interaction_accepts_yes_variants(monkeypatch, choice):
    messages = []
    monkeypatch.setattr(
        "cli.cli_interaction.cli.inform_system_info",
        messages.append,
    )
    monkeypatch.setattr(
        "cli.cli_interaction.cli.get_user_input",
        lambda prompt: choice,
    )

    response = CliInteraction().request_approval(request())

    assert response.approved is True
    assert any("dangerous command" in message for message in messages)
    assert any("powershell" in message for message in messages)


@pytest.mark.parametrize("choice", ["", "n", "no", "anything else"])
def test_cli_interaction_rejects_non_yes_input(monkeypatch, choice):
    monkeypatch.setattr(
        "cli.cli_interaction.cli.inform_system_info",
        lambda message: None,
    )
    monkeypatch.setattr(
        "cli.cli_interaction.cli.get_user_input",
        lambda prompt: choice,
    )

    response = CliInteraction().request_approval(request())

    assert response.approved is False

