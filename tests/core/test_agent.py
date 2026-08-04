import sys
import importlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

agent = importlib.import_module("core.agent")


def test_master_agent_builds_policy_from_config(monkeypatch):
    captured = {}
    outputs = []

    class FakeConfig:
        def get_model_config(self):
            return {
                "api": "openai",
                "model_url": "http://configured.example",
                "api_key": "configured-key",
                "model_name": "configured-model",
                "fallback_model_name": "fallback-model",
            }

        def get_content_length(self):
            return {"MAIN_OUTPUT_TOKENS": 1234}

    def fake_query_loop(policy, state):
        captured["policy"] = policy
        captured["state"] = state
        state["messages"].append({
            "role": "assistant",
            "content": [{"type": "text", "text": "done"}],
        })
        return state, {"reason": "completed"}

    inputs = iter(["hello", "q"])
    monkeypatch.setattr(agent.config, "Config", FakeConfig)
    monkeypatch.setattr(agent.cli, "get_user_input", lambda: next(inputs))
    monkeypatch.setattr(agent.cli, "inform_system_info", lambda message: None)
    monkeypatch.setattr(agent.cli, "put_agent_output", outputs.append)
    monkeypatch.setattr(agent.cli, "put_agent_other_info", lambda message: None)
    monkeypatch.setattr(agent.hook, "trigger_hooks", lambda *args: None)
    monkeypatch.setattr(agent.builtin, "update_context", lambda context, messages: context)
    monkeypatch.setattr(agent.tools, "TOOLS_LIST", [])
    monkeypatch.setattr(agent, "query_loop", fake_query_loop)

    agent.master_agent()

    assert captured["policy"]["model"] == {
        "api": "openai",
        "model_url": "http://configured.example",
        "api_key": "configured-key",
        "model_name": "configured-model",
        "fallback_model_name": "fallback-model",
    }
    assert captured["policy"]["fallback_model"] == {
        "api": "openai",
        "model_url": "http://configured.example",
        "api_key": "configured-key",
        "model_name": "fallback-model",
        "fallback_model_name": "fallback-model",
    }
    assert captured["state"]["max_output_tokens"] == 1234
    assert outputs == ["done"]
