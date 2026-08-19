import pytest

import cli.event_sink as event_sink
from event import EventType, make_event


class RuntimeStub:
    session_id = "session"
    agent_id = "agent"

    class State:
        turn_count = 1

    state = State()


@pytest.mark.parametrize(
    ("event_type", "data", "method", "expected"),
    [
        (EventType.SYSTEM_MESSAGE, {"trigger": "hello"}, "inform_system_info", "hello"),
        (EventType.ASSISTANT_MESSAGE, {"text": "done"}, "put_agent_output", "done"),
        (EventType.TOOL_REQUESTED, {"tool_name": "demo"}, "put_agent_other_info", "[TOOL]: demo"),
        (EventType.TOOL_BLOCKED, {"reason": "blocked"}, "put_agent_other_info", "[BLOCKED]: blocked"),
        (EventType.COMPACT_STARTED, {}, "put_agent_other_info", "[auto compact]"),
        (EventType.ERROR, {"message": "failed"}, "inform_system_warning", "failed"),
    ],
)
def test_cli_event_sink_dispatches_supported_events(
    monkeypatch,
    event_type,
    data,
    method,
    expected,
):
    calls = []
    monkeypatch.setattr(event_sink.cli, method, calls.append)

    event_sink.CliEventSink().emit(make_event(RuntimeStub(), event_type, **data))

    assert calls == [expected]


def test_cli_event_sink_truncates_tool_output(monkeypatch):
    calls = []
    monkeypatch.setattr(event_sink.cli, "put_agent_other_info", calls.append)

    event_sink.CliEventSink().emit(
        make_event(
            RuntimeStub(),
            EventType.TOOL_COMPLETED,
            output="x" * 250,
        )
    )

    assert calls == ["x" * 200]


def test_cli_event_sink_formats_todo_updated_event(monkeypatch):
    calls = []
    monkeypatch.setattr(event_sink.cli, "put_agent_output", calls.append)

    todos = [
        {"content": "read", "status": "pending"},
        {"content": "edit", "status": "in_progress"},
        {"content": "test", "status": "completed"},
    ]
    event_sink.CliEventSink().emit(
        make_event(RuntimeStub(), EventType.TODO_UPDATED, todos=todos)
    )

    assert calls == [
        "\033[33m## Current Tasks\033[0m\n"
        "    [ ] read\n"
        "    [\033[36m▸\033[0m] edit\n"
        "    [\033[32m✓\033[0m] test"
    ]


def test_cli_event_sink_ignores_unhandled_events(monkeypatch):
    calls = []
    for method in (
        "inform_system_info",
        "inform_system_warning",
        "put_agent_output",
        "put_agent_other_info",
    ):
        monkeypatch.setattr(event_sink.cli, method, calls.append)

    event_sink.CliEventSink().emit(
        make_event(RuntimeStub(), EventType.TURN_STARTED, trigger="turn")
    )
    event_sink.CliEventSink().emit(
        make_event(RuntimeStub(), EventType.COMPACT_COMPLETED, trigger="complete")
    )

    assert calls == []
