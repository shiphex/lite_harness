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


def test_spawn_subagent_returns_final_text(monkeypatch):
    monkeypatch.setattr(
        subagent.api,
        "call_model",
        lambda **kwargs: SimpleNamespace(
            content=[SimpleNamespace(type="text", text="final answer")],
            stop_reason="end_turn",
        ),
    )
    monkeypatch.setattr(subagent.cli, "put_agent_other_info", lambda message: None)

    result = subagent.spawn_subagent(
        ToolContext(SimpleNamespace(name="runtime")),
        "summarize the project",
    )

    assert result == "final answer"


def test_spawn_subagent_passes_context_to_nested_tool(monkeypatch):
    responses = iter([
        SimpleNamespace(
            content=[SimpleNamespace(
                type="tool_use",
                id="tool-1",
                name="test_tool",
                input={"value": "hello"},
            )],
            stop_reason="tool_use",
        ),
        SimpleNamespace(
            content=[SimpleNamespace(type="text", text="done")],
            stop_reason="end_turn",
        ),
    ])
    monkeypatch.setattr(subagent.api, "call_model", lambda **kwargs: next(responses))
    monkeypatch.setattr(subagent.hook, "trigger_hooks", lambda *args: None)
    monkeypatch.setattr(subagent.cli, "put_agent_other_info", lambda message: None)
    monkeypatch.setattr(subagent.tool_handler, "STANDARD_TOOLS_LIST", [])

    calls = []

    def handler(context, value):
        calls.append((context, value))
        return "tool result"

    monkeypatch.setattr(
        subagent.tool_handler,
        "STANDARD_TOOLS_HANDLERS",
        {"test_tool": handler},
    )
    context = ToolContext(SimpleNamespace(name="runtime"))

    assert subagent.spawn_subagent(context, "run a tool") == "done"
    assert calls == [(context, "hello")]


def test_spawn_subagent_records_blocked_tool_result(monkeypatch):
    responses = iter([
        SimpleNamespace(
            content=[SimpleNamespace(
                type="tool_use",
                id="tool-1",
                name="danger",
                input={},
            )],
            stop_reason="tool_use",
        ),
        SimpleNamespace(
            content=[SimpleNamespace(type="text", text="blocked")],
            stop_reason="end_turn",
        ),
    ])
    monkeypatch.setattr(subagent.api, "call_model", lambda **kwargs: next(responses))
    monkeypatch.setattr(subagent.hook, "trigger_hooks", lambda *args: "Permission denied")
    monkeypatch.setattr(subagent.cli, "put_agent_other_info", lambda message: None)

    assert subagent.spawn_subagent(
        ToolContext(SimpleNamespace()),
        "run a dangerous tool",
    ) == "blocked"
