from types import SimpleNamespace

from tools.subagent import extract_text
import tools.subagent as subagent
from tools.tool_class import ToolContext


def test_extract_text_handles_text_blocks_and_scalars():
    assert extract_text("hello") == "hello"
    assert extract_text(123) == "123"
    assert extract_text([ 
        SimpleNamespace(type="text", text="hello"),
        SimpleNamespace(type="tool_use", text="ignored"),
        SimpleNamespace(type="text", text="world"),
    ]) == "hello\nworld"
    assert extract_text([
        {"type": "text", "text": "hello"},
        {"type": "tool_use", "name": "ignored"},
        {"type": "text", "text": "world"},
    ]) == "hello\nworld"


def test_run_subagent_returns_text_from_query_loop_history(monkeypatch):
    runtime = SimpleNamespace(
        session_id="session",
        agent_id="agent",
        agent_name="subagent",
        state=SimpleNamespace(turn_count=0),
        paths=SimpleNamespace(workspace="workspace"),
        events=SimpleNamespace(emit=lambda event: None),
        hooks=SimpleNamespace(run=lambda *args: None),
    )
    final_state = SimpleNamespace(messages=[
        {
            "role": "assistant",
            "content": [{"type": "text", "text": "done"}],
        },
    ])

    monkeypatch.setattr(
        subagent,
        "create_subagent_runtime",
        lambda *args, **kwargs: runtime,
    )

    import core.loop as loop
    monkeypatch.setattr(
        loop,
        "query_loop",
        lambda current_runtime: (final_state, {"reason": "completed"}),
    )

    result = subagent.run_subagent(
        ToolContext(SimpleNamespace(name="runtime")),
        "complete the task",
    )

    assert result == "done"


def _patch_run_subagent(monkeypatch, messages, assertion=None):
    runtime = SimpleNamespace(
        session_id="session",
        agent_id="agent",
        agent_name="subagent",
        state=SimpleNamespace(turn_count=0, messages=[]),
        paths=SimpleNamespace(workspace="workspace"),
        events=SimpleNamespace(emit=lambda event: None),
        hooks=SimpleNamespace(run=lambda *args: None),
    )

    def create_runtime(history, *args, **kwargs):
        runtime.state.messages = history
        return runtime

    monkeypatch.setattr(subagent, "create_subagent_runtime", create_runtime)

    import core.loop as loop

    def query_loop(current_runtime):
        if assertion is not None:
            assertion(current_runtime)
        return SimpleNamespace(messages=messages), {"reason": "completed"}

    monkeypatch.setattr(loop, "query_loop", query_loop)


def test_run_subagent_passes_description_and_returns_final_text(monkeypatch):
    final_messages = [{
        "role": "assistant",
        "content": [{"type": "text", "text": "done"}],
    }]

    def assert_description(runtime):
        assert runtime.state.messages == [{
            "role": "user",
            "content": "complete the task",
        }]

    _patch_run_subagent(monkeypatch, final_messages, assert_description)

    result = subagent.run_subagent(
        ToolContext(SimpleNamespace(name="runtime")),
        "complete the task",
    )

    assert result == "done"


def test_run_subagent_finds_previous_assistant_text_after_tool_round(monkeypatch):
    messages = [
        {
            "role": "assistant",
            "content": [{"type": "text", "text": "done"}],
        },
        {
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": "tool-1",
                "content": "tool result",
            }],
        },
    ]
    _patch_run_subagent(monkeypatch, messages)

    result = subagent.run_subagent(
        ToolContext(SimpleNamespace(name="runtime")),
        "run a tool",
    )

    assert result == "done"


def test_run_subagent_returns_fallback_without_assistant_text(monkeypatch):
    messages = [{
        "role": "user",
        "content": [{
            "type": "tool_result",
            "tool_use_id": "tool-1",
            "content": "blocked",
        }],
    }]
    _patch_run_subagent(monkeypatch, messages)

    result = subagent.run_subagent(
        ToolContext(SimpleNamespace(name="runtime")),
        "run a blocked tool",
    )

    assert "未给出最终答案" in result
