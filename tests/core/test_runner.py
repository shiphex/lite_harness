from types import SimpleNamespace

from core import runner
from hook.hook_handler import HookEvent


def test_run_turn_executes_outer_lifecycle(monkeypatch):
    """run_turn 应按 Hook、消息、状态重置、query_loop 的顺序执行。"""

    calls = []
    runtime = SimpleNamespace(
        session_id="session",
        agent_id="agent",
        agent_name="agent",
        paths=SimpleNamespace(workspace="workspace"),
        state=SimpleNamespace(messages=[], turn_count=8),
        hooks=SimpleNamespace(
            run=lambda event, context, value: calls.append(
                ("hook", event, context, value)
            )
        ),
    )

    def begin_run():
        calls.append(("begin_run",))
        runtime.state.turn_count = 0

    runtime.begin_run = begin_run
    monkeypatch.setattr(runner.hook, "make_hook_context", lambda value: "hook-context")

    def query_loop(current_runtime):
        calls.append(("query_loop", list(current_runtime.state.messages)))
        return current_runtime.state, {"reason": "completed"}

    monkeypatch.setattr(runner, "query_loop", query_loop)

    result_state, status = runner.run_turn(runtime, "hello")

    assert result_state is runtime.state
    assert status == {"reason": "completed"}
    assert runtime.state.messages == [{"role": "user", "content": "hello"}]
    assert calls == [
        ("hook", HookEvent.USER_PROMPT_SUBMIT, "hook-context", "hello"),
        ("begin_run",),
        ("query_loop", [{"role": "user", "content": "hello"}]),
    ]
