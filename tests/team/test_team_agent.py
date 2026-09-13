from types import SimpleNamespace

import pytest

import core.loop as loop_module
import team.agent as agent_module
from team.agent import TeamAgent
from team.contracts import TeamError


def test_team_agent_run_uses_existing_query_loop_boundary(monkeypatch):
    calls = []
    runtime = SimpleNamespace(
        state=SimpleNamespace(messages=[], turn_count=9),
        hooks=SimpleNamespace(
            run=lambda event, context, prompt: calls.append(
                ("hook", event, context, prompt)
            )
        ),
    )
    runtime.begin_run = lambda: (
        calls.append(("begin",)),
        setattr(runtime.state, "turn_count", 0),
    )

    def run_loop(current_runtime):
        calls.append(("loop", current_runtime))
        return current_runtime.state, {"reason": "completed"}

    monkeypatch.setattr(
        agent_module.hook,
        "make_hook_context",
        lambda current_runtime: "hook-context",
    )
    agent = TeamAgent(runtime=runtime, run_loop=run_loop)

    result = agent.run("inspect the module")

    assert runtime.state.messages == [
        {"role": "user", "content": "inspect the module"}
    ]
    assert calls[0][0] == "hook"
    assert calls[0][2:] == ("hook-context", "inspect the module")
    assert calls[1] == ("begin",)
    assert calls[2] == ("loop", runtime)
    assert result == (runtime.state, {"reason": "completed"})


def test_team_agent_defaults_to_existing_query_loop(monkeypatch):
    calls = []
    runtime = SimpleNamespace(
        state=SimpleNamespace(messages=[]),
        hooks=SimpleNamespace(run=lambda *args: None),
        begin_run=lambda: None,
    )

    def fake_query_loop(current_runtime):
        calls.append(current_runtime)
        return current_runtime.state, {"reason": "completed"}

    monkeypatch.setattr(loop_module, "query_loop", fake_query_loop)
    monkeypatch.setattr(
        agent_module.hook,
        "make_hook_context",
        lambda current_runtime: "hook-context",
    )

    result = TeamAgent(runtime=runtime).run("inspect")

    assert calls == [runtime]
    assert result == (runtime.state, {"reason": "completed"})


@pytest.mark.parametrize("prompt", ["", "   ", None])
def test_team_agent_rejects_empty_prompt(prompt):
    agent = TeamAgent(runtime=SimpleNamespace())

    with pytest.raises(TeamError, match="prompt"):
        agent.run(prompt)
