from concurrent.futures import ThreadPoolExecutor

import pytest

from team.contracts import MemberEvent, MemberState, TransitionSource
from team.messaging import MessageBus
from team.registry import MemberRegistry


def _member(registry, agent_id, *, state=MemberState.IDLE):
    registry.register(agent_id, agent_id)
    if state is MemberState.STARTING:
        return
    registry.transition(
        agent_id,
        MemberEvent.SPAWN_SUCCESS,
        source=TransitionSource.LIFECYCLE_MANAGER,
    )
    if state is MemberState.STOPPED:
        registry.transition(
            agent_id, MemberEvent.SHUTDOWN, source=TransitionSource.LIFECYCLE_MANAGER
        )
    elif state is MemberState.FAILED:
        registry.transition(
            agent_id,
            MemberEvent.FATAL_RUNTIME_ERROR,
            source=TransitionSource.LIFECYCLE_MANAGER,
        )
    elif state in (MemberState.BUSY, MemberState.WAITING):
        registry.transition(
            agent_id,
            MemberEvent.TASK_CLAIMED,
            source=TransitionSource.TEAM_COORDINATOR,
        )
        if state is MemberState.WAITING:
            registry.transition(
                agent_id,
                MemberEvent.DEPENDENCY_WAIT,
                source=TransitionSource.TEAM_AGENT,
            )


def _bus_with_members(*, capacity=100):
    registry = MemberRegistry()
    _member(registry, "sender")
    _member(registry, "target")
    return registry, MessageBus(registry, capacity=capacity)


def test_handle_routes_fifo_messages_and_empty_receive_returns_none():
    registry, bus = _bus_with_members(capacity=2)
    sender = bus.bind("sender")
    target = bus.bind("target")

    sender.send("target", "first")
    sender.send("target", "second")

    first = target.receive()
    second = target.receive()
    assert (first.sender_id, first.target_id, first.content) == (
        "sender", "target", "first"
    )
    assert (second.sender_id, second.target_id, second.content) == (
        "sender", "target", "second"
    )
    assert target.receive() is None
    assert registry.get("sender").state is MemberState.IDLE
    assert registry.get("target").state is MemberState.IDLE


def test_full_mailbox_rejects_without_losing_queued_message():
    from team.contracts import MailboxFullError

    _, bus = _bus_with_members(capacity=1)
    bus.bind("sender").send("target", "keep")

    with pytest.raises(MailboxFullError):
        bus.bind("sender").send("target", "reject")

    assert bus.bind("target").receive().content == "keep"
    assert bus.bind("target").receive() is None


def test_default_capacity_rejects_message_101():
    from team.contracts import MailboxFullError

    _, bus = _bus_with_members()
    sender = bus.bind("sender")
    for number in range(100):
        sender.send("target", str(number))

    with pytest.raises(MailboxFullError):
        sender.send("target", "101")
    assert bus.bind("target").receive().content == "0"


@pytest.mark.parametrize("capacity", [0, -1, 1.5, True])
def test_capacity_must_be_a_positive_integer(capacity):
    with pytest.raises(ValueError):
        MessageBus(MemberRegistry(), capacity=capacity)


@pytest.mark.parametrize(
    "content",
    [None, 4, "", " \t ", "x" * 16_385],
    ids=["none", "number", "empty", "whitespace", "too_long"],
)
def test_invalid_content_is_rejected_before_enqueue(content):
    from team.contracts import InvalidMessageError

    _, bus = _bus_with_members()
    with pytest.raises(InvalidMessageError):
        bus.bind("sender").send("target", content)
    assert bus.bind("target").receive() is None


def test_content_at_length_limit_is_delivered():
    _, bus = _bus_with_members()
    bus.bind("sender").send("target", "x" * 16_384)
    assert len(bus.bind("target").receive().content) == 16_384


def test_unknown_target_and_sender_are_typed_failures():
    from team.contracts import MessageTargetNotFoundError, MessageUnavailableError

    _, bus = _bus_with_members()
    with pytest.raises(MessageTargetNotFoundError):
        bus.bind("sender").send("missing", "hello")
    with pytest.raises(MessageUnavailableError):
        bus.bind("missing").send("target", "hello")
    assert bus.bind("target").receive() is None


def test_noncanonical_ids_cannot_create_unreachable_mailboxes_or_sender_ids():
    from team.contracts import MessageTargetNotFoundError, MessageUnavailableError

    _, bus = _bus_with_members()
    with pytest.raises(MessageTargetNotFoundError):
        bus.bind("sender").send("target ", "lost")
    with pytest.raises(MessageUnavailableError):
        bus.bind("sender ").send("target", "spoof")
    with pytest.raises(MessageUnavailableError):
        bus.bind("target ").receive()
    assert bus.bind("target").receive() is None


@pytest.mark.parametrize("state", [MemberState.STARTING, MemberState.STOPPED, MemberState.FAILED])
def test_unavailable_target_rejects_without_enqueuing(state):
    from team.contracts import MessageUnavailableError

    registry = MemberRegistry()
    _member(registry, "sender")
    _member(registry, "target", state=state)
    bus = MessageBus(registry)

    with pytest.raises(MessageUnavailableError):
        bus.bind("sender").send("target", "hello")
    assert registry.get("target").state is state


@pytest.mark.parametrize("state", [MemberState.STARTING, MemberState.STOPPED, MemberState.FAILED])
def test_unavailable_sender_cannot_send_or_receive(state):
    from team.contracts import MessageUnavailableError

    registry = MemberRegistry()
    _member(registry, "sender", state=state)
    _member(registry, "target")
    bus = MessageBus(registry)

    with pytest.raises(MessageUnavailableError):
        bus.bind("sender").send("target", "hello")
    with pytest.raises(MessageUnavailableError):
        bus.bind("sender").receive()
    assert registry.get("sender").state is state


@pytest.mark.parametrize("state", [MemberState.BUSY, MemberState.WAITING])
def test_active_busy_or_waiting_member_can_receive(state):
    registry = MemberRegistry()
    _member(registry, "sender")
    _member(registry, "target", state=state)
    bus = MessageBus(registry)

    bus.bind("sender").send("target", "hello")
    assert bus.bind("target").receive().content == "hello"
    assert registry.get("target").state is state


@pytest.mark.parametrize("state", [MemberState.BUSY, MemberState.WAITING])
def test_active_busy_or_waiting_member_can_send(state):
    registry = MemberRegistry()
    _member(registry, "sender", state=state)
    _member(registry, "target")
    bus = MessageBus(registry)

    bus.bind("sender").send("target", "hello")
    assert bus.bind("target").receive().sender_id == "sender"
    assert registry.get("sender").state is state


def test_separate_buses_cannot_route_to_other_teams_member():
    from team.contracts import MessageTargetNotFoundError

    first_registry = MemberRegistry()
    second_registry = MemberRegistry()
    _member(first_registry, "sender")
    _member(second_registry, "other-team-target")
    first_bus = MessageBus(first_registry)
    second_bus = MessageBus(second_registry)

    with pytest.raises(MessageTargetNotFoundError):
        first_bus.bind("sender").send("other-team-target", "hello")
    assert second_bus.bind("other-team-target").receive() is None


def test_concurrent_sends_do_not_lose_messages():
    _, bus = _bus_with_members(capacity=40)
    sender = bus.bind("sender")
    target = bus.bind("target")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda number: sender.send("target", str(number)), range(40)))

    assert {target.receive().content for _ in range(40)} == {
        str(number) for number in range(40)
    }
    assert target.receive() is None


def test_team_package_exposes_message_contract_for_callers():
    from team import (
        InvalidMessageError,
        MailboxFullError,
        MailboxHandle,
        MessageTargetNotFoundError,
        MessageUnavailableError,
        TeamError,
        TeamMessage,
    )

    _, bus = _bus_with_members()
    sender = bus.bind("sender")
    sender.send("target", "hello")

    assert isinstance(sender, MailboxHandle)
    assert isinstance(bus.bind("target").receive(), TeamMessage)
    assert all(
        issubclass(error, TeamError)
        for error in (
            InvalidMessageError,
            MailboxFullError,
            MessageTargetNotFoundError,
            MessageUnavailableError,
        )
    )
