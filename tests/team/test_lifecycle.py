from types import SimpleNamespace

import pytest

from builtin.memory import MemoryMode
from event.interaction import NonInteractiveInteraction
from event.sink import NullEventSink
from team.agent import TeamAgent
from team.contracts import (
    DuplicateMemberError,
    InvalidMemberTransitionError,
    MemberState,
    SpawnError,
)
from team.lifecycle import LifecycleManager
from team.registry import MemberRegistry


def _parent_runtime(tmp_path, *, session_id="session-1"):
    return SimpleNamespace(
        session_id=session_id,
        policy=SimpleNamespace(
            model={"api": "fake", "model_name": "primary"},
            fallback_model={"api": "fake", "model_name": "fallback"},
        ),
        state=SimpleNamespace(max_output_tokens=2048),
        paths=SimpleNamespace(workspace=tmp_path),
    )


class RecordingRuntimeFactory:
    calls = []

    @classmethod
    def create(cls, **kwargs):
        cls.calls.append(kwargs)
        return SimpleNamespace(
            agent_id=f"{kwargs['agent_name']}-runtime-id",
            agent_name=kwargs["agent_name"],
            session_id=kwargs["session_id"],
            policy=kwargs["policy"],
            state=kwargs["state"],
            paths=SimpleNamespace(workspace=kwargs["workspace"]),
        )


def test_spawn_creates_idle_member_and_phase_two_runtime_policy(tmp_path):
    RecordingRuntimeFactory.calls = []
    registry = MemberRegistry()
    lifecycle = LifecycleManager(
        member_registry=registry,
        runtime_factory=RecordingRuntimeFactory,
        session_id="session-1",
    )

    member = lifecycle.spawn(
        parent_runtime=_parent_runtime(tmp_path),
        agent_name="researcher",
    )

    assert member.agent_id == "researcher-runtime-id"
    assert member.agent_name == "researcher"
    assert member.state is MemberState.IDLE
    assert registry.get(member.agent_id) is member
    assert isinstance(lifecycle._agents[member.agent_id], TeamAgent)

    call = RecordingRuntimeFactory.calls[0]
    assert call["session_id"] == "session-1"
    assert call["workspace"] == tmp_path
    assert call["policy"].model == {"api": "fake", "model_name": "primary"}
    assert call["policy"].fallback_model == {
        "api": "fake",
        "model_name": "fallback",
    }
    assert call["policy"].max_turns == 30
    assert call["policy"].can_ask_user is False
    assert {tool["name"] for tool in call["policy"].tools_list} == {
        "read_file",
        "glob",
        "load_skill",
    }
    assert set(call["policy"].tool_handler) == {
        "read_file",
        "glob",
        "load_skill",
    }
    assert call["state"].messages == []
    assert call["state"].context == {}
    assert call["state"].max_output_tokens == 2048
    assert call["memory_policy"].mode is MemoryMode.READ_ONLY
    assert call["memory_policy"].namespace == "master"
    assert isinstance(call["events"], NullEventSink)
    assert isinstance(call["interaction"], NonInteractiveInteraction)


class ExplodingRuntimeFactory:
    @staticmethod
    def create(**kwargs):
        raise RuntimeError("runtime exploded")


def test_spawn_runtime_failure_leaves_no_member_or_agent(tmp_path):
    registry = MemberRegistry()
    lifecycle = LifecycleManager(
        member_registry=registry,
        runtime_factory=ExplodingRuntimeFactory,
        session_id="session-1",
    )

    with pytest.raises(SpawnError, match="runtime creation"):
        lifecycle.spawn(
            parent_runtime=_parent_runtime(tmp_path),
            agent_name="researcher",
        )

    assert registry.list() == ()
    assert lifecycle._agents == {}


class ExplodingRegistry(MemberRegistry):
    def register(self, agent_id: str, agent_name: str):
        raise DuplicateMemberError("register exploded")


def test_register_failure_releases_unpublished_runtime(tmp_path):
    registry = ExplodingRegistry()
    lifecycle = LifecycleManager(
        member_registry=registry,
        runtime_factory=RecordingRuntimeFactory,
        session_id="session-1",
    )

    with pytest.raises(SpawnError, match="member registration"):
        lifecycle.spawn(
            parent_runtime=_parent_runtime(tmp_path),
            agent_name="researcher",
        )

    assert registry.list() == ()
    assert lifecycle._agents == {}


class ExplodingTransitionRegistry(MemberRegistry):
    def transition(self, agent_id, event, *, source):
        raise InvalidMemberTransitionError("commit exploded")


def test_commit_failure_rolls_back_starting_member_and_agent(tmp_path):
    registry = ExplodingTransitionRegistry()
    lifecycle = LifecycleManager(
        member_registry=registry,
        runtime_factory=RecordingRuntimeFactory,
        session_id="session-1",
    )

    with pytest.raises(SpawnError, match="member commit"):
        lifecycle.spawn(
            parent_runtime=_parent_runtime(tmp_path),
            agent_name="researcher",
        )

    assert registry.list() == ()
    assert lifecycle._agents == {}


def test_wrapper_creation_failure_leaves_no_member_or_agent(tmp_path):
    def explode(**kwargs):
        raise RuntimeError("wrapper exploded")

    registry = MemberRegistry()
    lifecycle = LifecycleManager(
        member_registry=registry,
        runtime_factory=RecordingRuntimeFactory,
        session_id="session-1",
        agent_factory=explode,
    )

    with pytest.raises(SpawnError, match="wrapper creation"):
        lifecycle.spawn(
            parent_runtime=_parent_runtime(tmp_path),
            agent_name="researcher",
        )

    assert registry.list() == ()
    assert lifecycle._agents == {}


@pytest.mark.parametrize("agent_name", ["", "../escape", "two words", "_hidden"])
def test_spawn_rejects_unsafe_agent_name_before_runtime_creation(
    tmp_path,
    agent_name,
):
    RecordingRuntimeFactory.calls = []
    lifecycle = LifecycleManager(
        member_registry=MemberRegistry(),
        runtime_factory=RecordingRuntimeFactory,
        session_id="session-1",
    )

    with pytest.raises(SpawnError, match="agent_name"):
        lifecycle.spawn(
            parent_runtime=_parent_runtime(tmp_path),
            agent_name=agent_name,
        )

    assert RecordingRuntimeFactory.calls == []


def test_spawn_rejects_parent_from_another_team_session(tmp_path):
    lifecycle = LifecycleManager(
        member_registry=MemberRegistry(),
        runtime_factory=RecordingRuntimeFactory,
        session_id="session-1",
    )

    with pytest.raises(SpawnError, match="session"):
        lifecycle.spawn(
            parent_runtime=_parent_runtime(tmp_path, session_id="other-session"),
            agent_name="researcher",
        )
