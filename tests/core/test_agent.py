from pathlib import Path
from types import SimpleNamespace

import pytest

from core import agent
from core.runtime import state
from event import EventType, make_event


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

        def get_team_config(self):
            return {"MAX_MEMBERS": 3}

    return FakeConfig


def test_create_master_runtime_builds_policy_and_state(monkeypatch, tmp_path):
    monkeypatch.setattr(agent.config, "Config", _config(tmp_path))
    monkeypatch.setattr(agent.tools, "TOOLS_LIST", [{"name": "demo_tool"}])
    monkeypatch.setattr(
        agent.tools,
        "TOOLS_HANDLERS",
        {"demo_tool": lambda context: "ok"},
    )

    events = object()
    interaction = object()
    runtime = agent.create_master_runtime(
        [],
        {},
        events=events,
        interaction=interaction,
    )

    assert runtime.policy.model["model_name"] == "configured-model"
    assert runtime.policy.fallback_model["model_name"] == "fallback-model"
    assert runtime.policy.tools_list == [{"name": "demo_tool"}]
    assert runtime.state.current_model == runtime.policy.model
    assert runtime.state.max_output_tokens == 1234
    assert runtime.state.recovery_count == 0
    assert runtime.paths.workspace == tmp_path
    assert runtime.events is events
    assert runtime.interaction is interaction


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
    created_with = {}
    close_calls = []
    captured = {}
    context_updates = []

    def fake_run_turn(current_runtime, user_input):
        captured["runtime"] = current_runtime
        captured["user_input"] = user_input
        current_runtime.state.turn_count = 0
        current_runtime.state.messages.append({
            "role": "user",
            "content": user_input,
        })
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

    def fake_create_session(history, context, **kwargs):
        created_with.update(kwargs)
        runtime.state.messages = history
        runtime.state.context = context
        return SimpleNamespace(
            runtime=runtime,
            team="team",
            close=lambda: close_calls.append(True),
        )

    class FakeDriver:
        def __init__(self, *, runtime, team):
            captured["driver_runtime"] = runtime
            captured["team"] = team

        def submit(self, user_input):
            return fake_run_turn(runtime, user_input)

    monkeypatch.setattr(agent, "create_master_session", fake_create_session)
    monkeypatch.setattr(agent, "SessionDriver", FakeDriver)
    monkeypatch.setattr(
        agent.builtin,
        "update_context",
        lambda context, **kwargs: context_updates.append((context, kwargs)) or context,
    )

    agent.master_agent()

    assert captured["runtime"] is runtime
    assert captured["user_input"] == "hello"
    assert captured["driver_runtime"] is runtime
    assert captured["team"] == "team"
    assert set(created_with) == {"events", "interaction"}
    assert close_calls == [True]
    assert runtime.state.messages[0] == {"role": "user", "content": "hello"}
    assert len(context_updates) == 2
    assert context_updates[0] == ({}, {})
    assert context_updates[-1][1]["memory_index"] == runtime.memory.index_path
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
    close_calls = []
    monkeypatch.setattr(
        agent,
        "create_master_session",
        lambda history, context, **kwargs: SimpleNamespace(
            runtime=runtime,
            team=object(),
            close=lambda: close_calls.append(True),
        ),
    )
    monkeypatch.setattr(agent.builtin, "update_context", lambda *args, **kwargs: {})

    agent.master_agent()

    assert [item.type for item in events] == [EventType.SYSTEM_MESSAGE]
    assert close_calls == [True]


def test_create_master_session_adds_team_tools(monkeypatch, tmp_path):
    monkeypatch.setattr(agent.config, "Config", _config(tmp_path))

    session = agent.create_master_session(
        [],
        {},
        events=SimpleNamespace(emit=lambda event: None),
        interaction=SimpleNamespace(),
    )
    tool_names = {tool["name"] for tool in session.runtime.policy.tools_list}

    assert session.runtime.session_id in session.team.team_id
    assert session.team.max_members == 3
    assert {
        "spawn_teammate",
        "send_message",
        "read_messages",
        "list_team",
        "shutdown_teammate",
        "wait_teammates",
    } <= tool_names
    assert "wait_teammates" in session.runtime.policy.prompt
    assert "禁止通过 read_messages" in session.runtime.policy.prompt
    assert session.runtime.agent_name == "lead"
    assert session.team._lead_agent_id == session.runtime.agent_id
    assert session.team._session_id == session.runtime.session_id
    session.close()
