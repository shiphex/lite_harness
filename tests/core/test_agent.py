from pathlib import Path
from types import SimpleNamespace

from core import agent
from core.runtime import state
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
    monkeypatch.setattr(agent.tools, "TOOLS_HANDLERS", {"demo_tool": lambda: "ok"})

    runtime = agent.create_master_runtime([], {})

    assert runtime.policy.model["model_name"] == "configured-model"
    assert runtime.policy.fallback_model["model_name"] == "fallback-model"
    assert runtime.policy.tools_list == [{"name": "demo_tool"}]
    assert runtime.state.current_model == runtime.policy.model
    assert runtime.state.max_output_tokens == 1234
    assert runtime.state.recovery_count == 0
    assert runtime.paths.workspace == tmp_path


def test_master_agent_passes_runtime_and_outputs_final_text(monkeypatch, tmp_path):
    runtime = SimpleNamespace(
        state=state(
            messages=[],
            context={},
            turn_count=17,
            current_model={"model_name": "model"},
        ),
        memory=SimpleNamespace(index_path=tmp_path / "MEMORY.md"),
    )
    hook_calls = []
    runtime.hooks = SimpleNamespace(
        run=lambda event, context, *args: hook_calls.append((event, context, args))
    )
    captured = {}
    outputs = []
    context_updates = []

    def fake_query_loop(current_runtime):
        captured["runtime"] = current_runtime
        assert current_runtime.state.turn_count == 0
        current_runtime.state.messages.append({
            "role": "assistant",
            "content": [{"type": "text", "text": "done"}],
        })
        return current_runtime.state, {"reason": "completed"}

    inputs = iter(["hello", "q"])
    def fake_create_runtime(history, context):
        runtime.state.messages = history
        runtime.state.context = context
        return runtime

    monkeypatch.setattr(agent, "create_master_runtime", fake_create_runtime)
    monkeypatch.setattr(agent, "query_loop", fake_query_loop)
    monkeypatch.setattr(agent.cli, "get_user_input", lambda: next(inputs))
    monkeypatch.setattr(agent.cli, "inform_system_info", lambda message: None)
    monkeypatch.setattr(agent.cli, "put_agent_output", outputs.append)
    monkeypatch.setattr(agent.cli, "put_agent_other_info", lambda message: None)
    monkeypatch.setattr(agent.hook, "make_hook_context", lambda current_runtime: "hook-context")
    monkeypatch.setattr(
        agent.builtin,
        "update_context",
        lambda context, messages, **kwargs: context_updates.append((context, messages, kwargs)) or context,
    )

    agent.master_agent()

    assert captured["runtime"] is runtime
    assert outputs == ["done"]
    assert runtime.state.messages[0] == {"role": "user", "content": "hello"}
    assert hook_calls == [
        (HookEvent.USER_PROMPT_SUBMIT, "hook-context", ("hello",)),
    ]
    assert len(context_updates) == 2
    assert context_updates[-1][2]["memory_index"] == runtime.memory.index_path
