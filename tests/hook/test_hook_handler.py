from hook.hook_handler import register_hook, trigger_hooks, HOOK
from hook.permission_hook import permission_hook
from types import SimpleNamespace


def test_register_hook():
    register_hook("UserPromptSubmit", "test_func")
    assert HOOK["UserPromptSubmit"][-1] == "test_func"


def test_trigger_hooks(monkeypatch):
    register_hook("PreToolUse", permission_hook)
    block = SimpleNamespace(
        name = "powershell",
        input = {"command": "rm test.txt"},
    )
    monkeypatch.setattr('builtins.input', lambda _: "N")
    result = trigger_hooks("PreToolUse", block)
    assert result == "权限已被用户拒绝"
