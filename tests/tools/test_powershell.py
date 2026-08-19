from types import SimpleNamespace

import tools.powershell as powershell
from tools.tool_class import ToolContext


def test_run_powershell_returns_command_output(monkeypatch):
    class Result:
        stdout = "output"
        stderr = ""

    calls = []
    monkeypatch.setattr(
        powershell.subprocess,
        "run",
        lambda command, **kwargs: calls.append((command, kwargs)) or Result(),
    )

    result = powershell.run_powershell(
        ToolContext(SimpleNamespace()),
        "Get-ChildItem",
    )

    assert result == "output"
    assert calls[0][0][-1] == "Get-ChildItem"


def test_run_powershell_rejects_dangerous_command(monkeypatch):
    monkeypatch.setattr(
        powershell.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()),
    )

    result = powershell.run_powershell(
        ToolContext(SimpleNamespace()),
        "sudo reboot",
    )

    assert "危险命令" in result
