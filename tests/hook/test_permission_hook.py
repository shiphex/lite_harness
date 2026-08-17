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
