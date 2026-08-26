from types import SimpleNamespace

from hook.hook_handler import HookAction
from hook.permission_hook import permission_hook


def block(command, *, name="powershell"):
    return SimpleNamespace(name=name, input={"command": command})


def test_permission_hook_blocks_deny_list_command():
    result = permission_hook(None, block("rm -rf /"))

    assert result.action == HookAction.BLOCK
    assert result.blocked is True
    assert result.approval_required is False
    assert "拒绝列表" in result.message


def test_permission_hook_asks_for_dangerous_command():
    result = permission_hook(None, block("Remove-Item test.py"))

    assert result.action == HookAction.ASK
    assert result.blocked is False
    assert result.approval_required is True
    assert "潜在破坏性指令" in result.message


def test_permission_hook_allows_safe_command():
    result = permission_hook(None, block("Get-ChildItem"))

    assert result.action == HookAction.CONTINUE
    assert result.blocked is False
    assert result.approval_required is False


def test_permission_hook_requires_spawn_teammate_approval():
    result = permission_hook(
        None,
        SimpleNamespace(
            name="spawn_teammate",
            input={"name": "alice", "role": "reviewer", "prompt": "review"},
        ),
    )

    assert result.action == HookAction.ASK
    assert result.approval_required is True
    assert "teammate" in result.message


def test_file_permission_uses_runtime_workspace(tmp_path):
    context = SimpleNamespace(workspace=tmp_path / "teammate")
    context.workspace.mkdir()
    block = SimpleNamespace(
        name="write_file",
        input={"path": str(tmp_path / "outside.txt"), "content": "x"},
    )

    result = permission_hook(context, block)

    assert result.action == HookAction.ASK
    assert "超出工作目录" in result.message
