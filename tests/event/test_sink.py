from event import (
    EventType,
    FanoutEventSink,
    MemoryEventSink,
    NullEventSink,
    SynchronizedEventSink,
    make_event,
)


class RuntimeStub:
    session_id = "session"
    agent_id = "agent"

    class State:
        turn_count = 1

    state = State()


def test_memory_event_sink_stores_and_clears_events():
    sink = MemoryEventSink()
    event = make_event(RuntimeStub(), EventType.TURN_STARTED)

    sink.emit(event)
    assert sink.events == [event]

    sink.clear()
    assert sink.events == []


def test_null_event_sink_discards_events():
    sink = NullEventSink()
    sink.emit(make_event(RuntimeStub(), EventType.TURN_STARTED))


def test_fanout_event_sink_forwards_to_every_sink():
    first = MemoryEventSink()
    second = MemoryEventSink()
    sink = FanoutEventSink(first, second)
    event = make_event(RuntimeStub(), EventType.TOOL_REQUESTED)

    sink.emit(event)

    assert first.events == [event]
    assert second.events == [event]


def test_synchronized_event_sink_forwards_event():
    memory = MemoryEventSink()
    sink = SynchronizedEventSink(memory)
    event = make_event(RuntimeStub(), EventType.TEAM_MEMBER_SPAWNED)

    sink.emit(event)

    assert memory.events == [event]

