from pathlib import Path
from types import SimpleNamespace

from hook.hook_handler import (
    HOOK,
    HookAction,
    HookContext,
    HookEvent,
    HookManager,
    HookResult,
    create_default_hooks,
    register_hook,
    trigger_hooks,
)
from hook.permission_hook import permission_hook


def make_context():
    return HookContext(
        session_id="session",
        agent_id="agent-id",
        agent_name="agent",
        turn_count=2,
        workspace=Path("."),
    )


def test_hook_result_defaults_to_continue():
    result = HookResult()

    assert result.action == HookAction.CONTINUE
    assert result.blocked is False
    assert result.approval_required is False


def test_hook_manager_runs_callbacks_and_short_circuits_on_action():
    manager = HookManager()
    calls = []
    block = SimpleNamespace(name="demo_tool", input={})

    def continue_callback(ctx, current_block):
        calls.append("continue")
        return HookResult()

    def ask_callback(ctx, current_block):
        calls.append("ask")
        return HookResult(action=HookAction.ASK, message="confirm")

    def unreachable_callback(ctx, current_block):
        calls.append("unreachable")
        return HookResult(action=HookAction.BLOCK)

    manager.register(HookEvent.PRE_TOOL_USE, continue_callback)
    manager.register(HookEvent.PRE_TOOL_USE, ask_callback)
    manager.register(HookEvent.PRE_TOOL_USE, unreachable_callback)

    result = manager.run(HookEvent.PRE_TOOL_USE, make_context(), block)

    assert result.action == HookAction.ASK
    assert result.message == "confirm"
    assert calls == ["continue", "ask"]


def test_create_default_hooks_registers_runtime_callbacks():
    manager = create_default_hooks()

    assert len(manager._hooks[HookEvent.USER_PROMPT_SUBMIT]) == 1
    assert manager._hooks[HookEvent.PRE_TOOL_USE] == [permission_hook]
    assert len(manager._hooks[HookEvent.POST_TOOL_USE]) == 1
    assert len(manager._hooks[HookEvent.STOP]) == 1
    assert all(
        callback.__name__ != "log_hook"
        for callbacks in manager._hooks.values()
        for callback in callbacks
    )


def test_legacy_trigger_hooks_accepts_runtime_context():
    block = SimpleNamespace(
        name="powershell",
        input={"command": "Remove-Item test.txt"},
    )

    result = trigger_hooks("PreToolUse", make_context(), block)

    assert result.action == HookAction.ASK


def test_register_hook_keeps_legacy_registry_contract():
    callback = lambda *args: None

    register_hook("UserPromptSubmit", callback)

    assert HOOK["UserPromptSubmit"][-1] is callback
