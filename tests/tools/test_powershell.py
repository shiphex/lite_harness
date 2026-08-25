from types import SimpleNamespace

import tools.powershell as powershell
from tools.tool_class import ToolContext


class FakeProcess:
    pid = 1234
    returncode = 0

    def __init__(self):
        self.terminated = False
        self.waited = False

    def communicate(self, timeout):
        return "output", ""

    def poll(self):
        return None if not self.terminated else 0

    def terminate(self):
        self.terminated = True

    def wait(self, timeout):
        self.waited = True


def test_run_process_uses_powershell_and_windows_process_group(monkeypatch):
    calls = []
    process = FakeProcess()

    monkeypatch.setattr(
        powershell.config,
        "get_system_info",
        lambda: {
            "system": "Windows",
            "shell_name": "PowerShell",
            "executable": "powershell",
        },
    )
    monkeypatch.setattr(
        powershell.subprocess,
        "CREATE_NEW_PROCESS_GROUP",
        512,
        raising=False,
    )
    monkeypatch.setattr(
        powershell.subprocess,
        "Popen",
        lambda command, **kwargs: calls.append((command, kwargs)) or process,
    )
    monkeypatch.setattr(powershell, "_stop_process_group", lambda _: None)

    result = powershell._run_bash_process("Get-Process")

    assert result == ("output", 0)
    assert calls[0][0] == [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-Command",
        "Get-Process",
    ]
    assert calls[0][1]["shell"] is False
    assert calls[0][1]["creationflags"] == 512


def test_run_process_uses_bash_and_linux_process_group(monkeypatch):
    calls = []
    process = FakeProcess()

    monkeypatch.setattr(
        powershell.config,
        "get_system_info",
        lambda: {
            "system": "Linux",
            "shell_name": "Bash",
            "executable": "bash",
        },
    )
    monkeypatch.setattr(
        powershell.subprocess,
        "Popen",
        lambda command, **kwargs: calls.append((command, kwargs)) or process,
    )
    monkeypatch.setattr(powershell, "_stop_process_group", lambda _: None)

    result = powershell._run_bash_process("printf hello")

    assert result == ("output", 0)
    assert calls[0][0] == ["bash", "-lc", "printf hello"]
    assert calls[0][1]["shell"] is False
    assert calls[0][1]["start_new_session"] is True


def test_stop_process_group_uses_taskkill_on_windows(monkeypatch):
    calls = []
    process = FakeProcess()

    monkeypatch.setattr(
        powershell.config,
        "get_system_info",
        lambda: {
            "system": "Windows",
            "shell_name": "PowerShell",
            "executable": "powershell",
        },
    )
    monkeypatch.setattr(
        powershell.subprocess,
        "run",
        lambda command, **kwargs: calls.append((command, kwargs))
        or SimpleNamespace(returncode=0),
    )

    powershell._stop_process_group(process)

    assert calls[0][0] == ["taskkill", "/PID", "1234", "/T", "/F"]
    assert calls[0][1]["check"] is False


def test_stop_process_group_falls_back_to_process_termination(monkeypatch):
    process = FakeProcess()

    monkeypatch.setattr(
        powershell.config,
        "get_system_info",
        lambda: {
            "system": "Windows",
            "shell_name": "PowerShell",
            "executable": "powershell",
        },
    )
    monkeypatch.setattr(
        powershell.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError()),
    )

    powershell._stop_process_group(process)

    assert process.terminated is True


def test_background_manager_collects_completed_task(monkeypatch):
    manager = powershell.BackgroundManager()
    manager.tasks["bg_0001"] = {
        "tool_use_id": "tool-1",
        "command": "printf done",
        "status": "running",
    }
    monkeypatch.setattr(
        powershell,
        "_run_bash_process",
        lambda command: ("done", 0),
    )

    manager._run("bg_0001", "printf done")

    notifications = manager.collect()

    assert len(notifications) == 1
    assert "<task_id>bg_0001</task_id>" in notifications[0]
    assert "<status>completed</status>" in notifications[0]
    assert "<summary>done</summary>" in notifications[0]
    assert "bg_0001" not in manager.tasks


def test_background_manager_marks_nonzero_exit_as_failed(monkeypatch):
    manager = powershell.BackgroundManager()
    manager.tasks["bg_0001"] = {
        "tool_use_id": "tool-1",
        "command": "false",
        "status": "running",
    }
    monkeypatch.setattr(
        powershell,
        "_run_bash_process",
        lambda command: ("failed", 1),
    )

    manager._run("bg_0001", "false")

    assert "<status>failed</status>" in manager.collect()[0]


def test_run_powershell_returns_command_output(monkeypatch):
    class Result:
        stdout = "output"
        stderr = ""

    calls = []
    monkeypatch.setattr(
        powershell.config,
        "get_system_info",
        lambda: {
            "system": "Windows",
            "shell_name": "PowerShell",
            "executable": "powershell",
        },
    )
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
    assert calls[0][0] == [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-Command",
        "Get-ChildItem",
    ]


def test_run_powershell_uses_bash_on_linux(monkeypatch):
    class Result:
        stdout = "output"
        stderr = ""

    calls = []
    monkeypatch.setattr(
        powershell.config,
        "get_system_info",
        lambda: {
            "system": "Linux",
            "shell_name": "Bash",
            "executable": "bash",
        },
    )
    monkeypatch.setattr(
        powershell.subprocess,
        "run",
        lambda command, **kwargs: calls.append((command, kwargs)) or Result(),
    )

    result = powershell.run_powershell(
        ToolContext(SimpleNamespace()),
        "printf hello",
    )

    assert result == "output"
    assert calls[0][0] == ["bash", "-lc", "printf hello"]


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
