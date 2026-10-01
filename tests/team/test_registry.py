from dataclasses import FrozenInstanceError

import pytest

from team.contracts import (
    DuplicateMemberError,
    InvalidMemberTransitionError,
    MemberEvent,
    MemberNotFoundError,
    MemberState,
    TransitionSource,
    UnauthorizedMemberOperationError,
    UnregisterReason,
)
from team.registry import MemberRegistry


def _registry_in_state(state: MemberState) -> MemberRegistry:
    registry = MemberRegistry()
    registry.register("agent-1", "teammate")
    if state is MemberState.STARTING:
        return registry

    registry.transition(
        "agent-1",
        MemberEvent.SPAWN_SUCCESS,
        source=TransitionSource.LIFECYCLE_MANAGER,
    )
    if state is MemberState.IDLE:
        return registry
    if state is MemberState.FAILED:
        registry.transition(
            "agent-1",
            MemberEvent.FATAL_RUNTIME_ERROR,
            source=TransitionSource.RUNTIME_SUPERVISOR,
        )
        return registry
    if state is MemberState.STOPPED:
        registry.transition(
            "agent-1",
            MemberEvent.SHUTDOWN,
            source=TransitionSource.LIFECYCLE_MANAGER,
        )
        return registry

    registry.transition(
        "agent-1",
        MemberEvent.TASK_CLAIMED,
        source=TransitionSource.TEAM_COORDINATOR,
    )
    if state is MemberState.BUSY:
        return registry

    registry.transition(
        "agent-1",
        MemberEvent.DEPENDENCY_WAIT,
        source=TransitionSource.TEAM_AGENT,
    )
    return registry


def test_registry_starts_empty_and_registers_immutable_starting_record():
    registry = MemberRegistry()

    assert registry.list() == ()

    member = registry.register("agent-1", "researcher")

    assert registry.get("agent-1") is member
    assert registry.get_member_state("agent-1") is MemberState.STARTING
    with pytest.raises(FrozenInstanceError):
        member.state = MemberState.IDLE


@pytest.mark.parametrize(
    ("initial", "event", "source", "expected"),
    [
        (
            MemberState.STARTING,
            MemberEvent.SPAWN_SUCCESS,
            TransitionSource.LIFECYCLE_MANAGER,
            MemberState.IDLE,
        ),
        (
            MemberState.IDLE,
            MemberEvent.TASK_CLAIMED,
            TransitionSource.TEAM_COORDINATOR,
            MemberState.BUSY,
        ),
        (
            MemberState.BUSY,
            MemberEvent.DEPENDENCY_WAIT,
            TransitionSource.TEAM_AGENT,
            MemberState.WAITING,
        ),
        (
            MemberState.WAITING,
            MemberEvent.DEPENDENCY_RESOLVED,
            TransitionSource.TASK_STORE,
            MemberState.BUSY,
        ),
        (
            MemberState.WAITING,
            MemberEvent.DEPENDENCY_RESOLVED,
            TransitionSource.TEAM_COORDINATOR,
            MemberState.BUSY,
        ),
        (
            MemberState.BUSY,
            MemberEvent.TASK_FINISHED,
            TransitionSource.TEAM_AGENT,
            MemberState.IDLE,
        ),
        (
            MemberState.IDLE,
            MemberEvent.SHUTDOWN,
            TransitionSource.LIFECYCLE_MANAGER,
            MemberState.STOPPED,
        ),
        (
            MemberState.BUSY,
            MemberEvent.SHUTDOWN,
            TransitionSource.TEAM_COORDINATOR,
            MemberState.STOPPED,
        ),
        (
            MemberState.WAITING,
            MemberEvent.SHUTDOWN,
            TransitionSource.LIFECYCLE_MANAGER,
            MemberState.STOPPED,
        ),
        (
            MemberState.STOPPED,
            MemberEvent.SHUTDOWN,
            TransitionSource.TEAM_COORDINATOR,
            MemberState.STOPPED,
        ),
        (
            MemberState.FAILED,
            MemberEvent.SHUTDOWN,
            TransitionSource.LIFECYCLE_MANAGER,
            MemberState.FAILED,
        ),
        (
            MemberState.IDLE,
            MemberEvent.FATAL_RUNTIME_ERROR,
            TransitionSource.RUNTIME_SUPERVISOR,
            MemberState.FAILED,
        ),
        (
            MemberState.BUSY,
            MemberEvent.FATAL_RUNTIME_ERROR,
            TransitionSource.LIFECYCLE_MANAGER,
            MemberState.FAILED,
        ),
        (
            MemberState.WAITING,
            MemberEvent.FATAL_RUNTIME_ERROR,
            TransitionSource.RUNTIME_SUPERVISOR,
            MemberState.FAILED,
        ),
    ],
)
def test_registry_applies_allowed_transitions(initial, event, source, expected):
    registry = _registry_in_state(initial)

    updated = registry.transition("agent-1", event, source=source)

    assert updated.state is expected
    assert registry.get_member_state("agent-1") is expected


def test_unauthorized_transition_is_rejected_without_state_change():
    registry = _registry_in_state(MemberState.IDLE)
    before = registry.get("agent-1")

    with pytest.raises(UnauthorizedMemberOperationError):
        registry.transition(
            "agent-1",
            MemberEvent.TASK_CLAIMED,
            source=TransitionSource.TEAM_AGENT,
        )

    assert registry.get("agent-1") is before


def test_invalid_transition_is_rejected_without_state_change():
    registry = _registry_in_state(MemberState.STOPPED)
    before = registry.get("agent-1")

    with pytest.raises(InvalidMemberTransitionError):
        registry.transition(
            "agent-1",
            MemberEvent.TASK_CLAIMED,
            source=TransitionSource.TEAM_COORDINATOR,
        )

    assert registry.get("agent-1") is before


def test_terminal_records_remain_queryable():
    stopped = _registry_in_state(MemberState.IDLE)
    stopped.transition(
        "agent-1",
        MemberEvent.SHUTDOWN,
        source=TransitionSource.LIFECYCLE_MANAGER,
    )
    failed = _registry_in_state(MemberState.IDLE)
    failed.transition(
        "agent-1",
        MemberEvent.FATAL_RUNTIME_ERROR,
        source=TransitionSource.RUNTIME_SUPERVISOR,
    )

    assert stopped.get_member_state("agent-1") is MemberState.STOPPED
    assert failed.get_member_state("agent-1") is MemberState.FAILED


def test_unregister_enforces_rollback_and_release_boundaries():
    rollback = _registry_in_state(MemberState.STARTING)
    removed = rollback.unregister(
        "agent-1",
        reason=UnregisterReason.SPAWN_ROLLBACK,
    )
    assert removed is not None
    assert rollback.unregister(
        "agent-1",
        reason=UnregisterReason.SPAWN_ROLLBACK,
    ) is None

    published = _registry_in_state(MemberState.IDLE)
    with pytest.raises(UnauthorizedMemberOperationError):
        published.unregister(
            "agent-1",
            reason=UnregisterReason.SPAWN_ROLLBACK,
        )
    assert published.get_member_state("agent-1") is MemberState.IDLE

    published.transition(
        "agent-1",
        MemberEvent.SHUTDOWN,
        source=TransitionSource.LIFECYCLE_MANAGER,
    )
    published.unregister("agent-1", reason=UnregisterReason.TEAM_RELEASE)
    with pytest.raises(MemberNotFoundError):
        published.get("agent-1")


def test_duplicate_member_id_is_rejected():
    registry = MemberRegistry()
    registry.register("agent-1", "first")

    with pytest.raises(DuplicateMemberError):
        registry.register("agent-1", "second")
