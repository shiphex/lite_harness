from pathlib import Path
from types import SimpleNamespace

import tools.file_option as file_option
import tools.powershell as powershell
from tools.tool_class import ToolContext


def runtime_context(workspace: Path):
    return ToolContext(SimpleNamespace(paths=SimpleNamespace(workspace=workspace)))


def test_file_tools_use_runtime_workspace(tmp_path, monkeypatch):
    lead_workspace = tmp_path / "lead"
    teammate_workspace = tmp_path / "teammate"
    lead_workspace.mkdir()
    teammate_workspace.mkdir()
    (teammate_workspace / "note.txt").write_text("teammate", encoding="utf-8")
    monkeypatch.setattr(file_option, "WORKDIR", lead_workspace)

    context = runtime_context(teammate_workspace)
    assert file_option.run_read(context, "note.txt") == "teammate"
    file_option.run_write(context, "new.txt", "new")

    assert (teammate_workspace / "new.txt").read_text(encoding="utf-8") == "new"
    assert not (lead_workspace / "new.txt").exists()


def test_bash_uses_runtime_workspace(monkeypatch, tmp_path):
    captured = {}

    def fake_run(command, cwd=None):
        captured["command"] = command
        captured["cwd"] = cwd
        return "ok", 0

    monkeypatch.setattr(powershell, "_run_bash_process", fake_run)
    workspace = tmp_path / "teammate"
    workspace.mkdir()

    assert powershell.run_bash(runtime_context(workspace), "pwd") == "ok"
    assert captured == {"command": "pwd", "cwd": workspace}


def test_background_manager_keeps_runtime_workspace(monkeypatch, tmp_path):
    manager = powershell.BackgroundManager()
    workspace = tmp_path / "teammate"
    workspace.mkdir()
    block = SimpleNamespace(
        name="bash",
        id="tool-1",
        input={"command": "pwd"},
    )
    captured = {}

    def fake_run(command, cwd=None):
        captured["cwd"] = cwd
        return "ok", 0

    monkeypatch.setattr(powershell, "_run_bash_process", fake_run)
    task_id = manager.start(block, workspace=workspace)
    # Calling _run directly keeps the test deterministic; the spawned daemon
    # may already have completed, so only assert the workspace contract here.
    manager._run(task_id, "pwd", workspace)

    assert captured["cwd"] == workspace
