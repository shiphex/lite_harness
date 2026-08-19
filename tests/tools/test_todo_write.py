from types import SimpleNamespace

import pytest

import tools.todo_write as todo_write
from event import EventType, MemoryEventSink
from tools.tool_class import ToolContext


@pytest.fixture(autouse=True)
def reset_todos():
    original = getattr(todo_write, "CURRENT_TODOS", None)
    yield
    todo_write.CURRENT_TODOS = original


def make_context():
    runtime = SimpleNamespace(
        session_id="session",
        agent_id="agent",
        state=SimpleNamespace(turn_count=1),
        events=MemoryEventSink(),
    )
    return ToolContext(runtime)


def test_normalize_todos_accepts_valid_statuses():
    todos = [
        {"content": "read", "status": "pending"},
        {"content": "edit", "status": "in_progress"},
        {"content": "test", "status": "completed"},
    ]

    result, error = todo_write._normalize_todos(todos)

    assert result is todos
    assert error is None


@pytest.mark.parametrize("value", [None, 1, {}, ("task",)])
def test_normalize_todos_rejects_non_lists(value):
    result, error = todo_write._normalize_todos(value)

    assert result is None
    assert "必须是列表" in error


def test_normalize_todos_accepts_json_string():
    result, error = todo_write._normalize_todos(
        '[{"content": "read", "status": "pending"}]'
    )

    assert result == [{"content": "read", "status": "pending"}]
    assert error is None


def test_normalize_todos_rejects_invalid_status():
    result, error = todo_write._normalize_todos(
        [{"content": "read", "status": "invalid"}]
    )

    assert result is None
    assert "invalid" in error


def test_run_todo_write_updates_state_and_emits_todos_event():
    context = make_context()
    todos = [{"content": "read", "status": "pending"}]

    result = todo_write.run_todo_write(context, todos)

    assert result.startswith("更新 1")
    assert todo_write.CURRENT_TODOS == todos
    assert len(context.runtime.events.events) == 1
    assert context.runtime.events.events[0].type == EventType.TODO_UPDATED
    assert context.runtime.events.events[0].data == {"todos": todos}


def test_run_todo_write_accepts_empty_list_and_emits_todos_event():
    context = make_context()
    todo_write.CURRENT_TODOS = [{"content": "existing", "status": "pending"}]

    result = todo_write.run_todo_write(context, [])

    assert "0" in result
    assert todo_write.CURRENT_TODOS == []
    assert len(context.runtime.events.events) == 1
    assert context.runtime.events.events[0].type == EventType.TODO_UPDATED
    assert context.runtime.events.events[0].data == {"todos": []}


def test_run_todo_write_does_not_change_state_or_emit_on_error():
    context = make_context()
    original = [{"content": "existing", "status": "pending"}]
    todo_write.CURRENT_TODOS = original

    result = todo_write.run_todo_write(
        context,
        [{"content": "bad", "status": "invalid"}],
    )

    assert "invalid" in result
    assert todo_write.CURRENT_TODOS is original
    assert context.runtime.events.events == []
