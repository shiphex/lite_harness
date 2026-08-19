from pathlib import Path
from types import SimpleNamespace

import pytest

from core import agent
from core.runtime import state
from event import EventType, make_event
from cli.cli_interaction import CliInteraction
from cli.event_sink import CliEventSink
from hook.hook_handler import HookEvent


def _config(tmp_path):
    class FakeConfig:
        def get_model_config(self):
            return {
                "api": "fake",
                "model_url": "http://configured.example",
                "api_key": "configured-key",
                "model_name": "configured-model",
                "fallback_model_name": "fallback-model",
            }

        def get_content_length(self):
            return {"MAIN_OUTPUT_TOKENS": 1234}

        def get_path_config(self, name):
            assert name == "project_path"
            return tmp_path

    return FakeConfig


def test_create_master_runtime_builds_policy_and_state(monkeypatch, tmp_path):
    monkeypatch.setattr(agent.config, "Config", _config(tmp_path))
    monkeypatch.setattr(agent.tools, "TOOLS_LIST", [{"name": "demo_tool"}])
    monkeypatch.setattr(
        agent.tools,
        "TOOLS_HANDLERS",
        {"demo_tool": lambda context: "ok"},
    )

    runtime = agent.create_master_runtime([], {})

    assert runtime.policy.model["model_name"] == "configured-model"
    assert runtime.policy.fallback_model["model_name"] == "fallback-model"
    assert runtime.policy.tools_list == [{"name": "demo_tool"}]
    assert runtime.state.current_model == runtime.policy.model
    assert runtime.state.max_output_tokens == 1234
    assert runtime.state.recovery_count == 0
    assert runtime.paths.workspace == tmp_path
    assert isinstance(runtime.events, CliEventSink)
    assert isinstance(runtime.interaction, CliInteraction)


def test_master_agent_passes_runtime_and_outputs_final_text(monkeypatch, tmp_path):
    events = []
    inputs = iter(["hello", "q"])
    runtime = SimpleNamespace(
        session_id="session",
        agent_id="agent",
        state=state(
            messages=[],
            context={},
            turn_count=17,
            current_model={"model_name": "model"},
        ),
        memory=SimpleNamespace(index_path=tmp_path / "MEMORY.md"),
        events=SimpleNamespace(emit=events.append),
        interaction=SimpleNamespace(
            get_user_input=lambda message=">> ": next(inputs),
        ),
    )
    hook_calls = []
    runtime.hooks = SimpleNamespace(
        run=lambda event, context, *args: hook_calls.append((event, context, args))
    )
    captured = {}
    context_updates = []

    def fake_query_loop(current_runtime):
        captured["runtime"] = current_runtime
        assert current_runtime.state.turn_count == 0
        current_runtime.events.emit(
            make_event(current_runtime, EventType.RUN_STARTED)
        )
        current_runtime.state.messages.append({
            "role": "assistant",
            "content": [{"type": "text", "text": "done"}],
        })
        current_runtime.events.emit(
            make_event(
                current_runtime,
                EventType.RUN_COMPLETED,
                trigger="test run completed",
            )
        )
        return current_runtime.state, {"reason": "completed"}

    def fake_create_runtime(history, context):
        runtime.state.messages = history
        runtime.state.context = context
        return runtime

    monkeypatch.setattr(agent, "create_master_runtime", fake_create_runtime)
    monkeypatch.setattr(agent, "query_loop", fake_query_loop)
    monkeypatch.setattr(agent.hook, "make_hook_context", lambda current_runtime: "hook-context")
    monkeypatch.setattr(
        agent.builtin,
        "update_context",
        lambda context, messages, **kwargs: context_updates.append((context, messages, kwargs)) or context,
    )

    agent.master_agent()

    assert captured["runtime"] is runtime
    assert runtime.state.messages[0] == {"role": "user", "content": "hello"}
    assert hook_calls == [
        (HookEvent.USER_PROMPT_SUBMIT, "hook-context", ("hello",)),
    ]
    assert len(context_updates) == 2
    assert context_updates[-1][2]["memory_index"] == runtime.memory.index_path
    event_types = [item.type for item in events]
    assert event_types.count(EventType.SYSTEM_MESSAGE) == 1
    assert event_types.count(EventType.ASSISTANT_MESSAGE) == 1
    assert event_types.count(EventType.RUN_STARTED) == 1
    assert event_types.count(EventType.RUN_COMPLETED) == 1
    assert next(
        item for item in events if item.type == EventType.ASSISTANT_MESSAGE
    ).data == {"text": "done"}


@pytest.mark.parametrize("exit_input", ["q", "exit", "   "])
def test_master_agent_accepts_exit_inputs(monkeypatch, exit_input):
    events = []
    runtime = SimpleNamespace(
        session_id="session",
        agent_id="agent",
        state=SimpleNamespace(turn_count=0),
        events=SimpleNamespace(emit=events.append),
        interaction=SimpleNamespace(get_user_input=lambda message=">> ": exit_input),
    )
    monkeypatch.setattr(agent, "create_master_runtime", lambda history, context: runtime)
    monkeypatch.setattr(agent.builtin, "update_context", lambda *args, **kwargs: {})

    agent.master_agent()

    assert [item.type for item in events] == [EventType.SYSTEM_MESSAGE]
