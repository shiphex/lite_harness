from types import SimpleNamespace

from event import EventType, make_event


def test_event_type_exposes_structured_runtime_values():
    assert EventType.TOOL_REQUESTED == "tool.requested"
    assert EventType.TOOL_COMPLETED == "tool.completed"
    assert EventType.APPROVAL_REQUESTED == "approval.requested"
    assert EventType.APPROVAL_RESOLVED == "approval.resolved"


def test_make_event_adds_runtime_metadata_and_payload():
    runtime = SimpleNamespace(
        session_id="session-1",
        agent_id="agent-1",
        state=SimpleNamespace(turn_count=4),
    )

    event = make_event(
        runtime,
        EventType.TOOL_COMPLETED,
        tool_call_id="call-1",
        output="ok",
    )

    assert event.type == EventType.TOOL_COMPLETED
    assert event.session_id == "session-1"
    assert event.agent_id == "agent-1"
    assert event.turn == 4
    assert event.data == {"tool_call_id": "call-1", "output": "ok"}
    assert event.event_id
    assert event.timestamp.tzinfo is not None


def test_make_event_creates_unique_ids():
    runtime = SimpleNamespace(
        session_id="session-1",
        agent_id="agent-1",
        state=SimpleNamespace(turn_count=0),
    )

    first = make_event(runtime, EventType.TURN_STARTED)
    second = make_event(runtime, EventType.TURN_STARTED)

    assert first.event_id != second.event_id

