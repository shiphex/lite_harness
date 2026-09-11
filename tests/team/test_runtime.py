from core.runtime import AgentRuntime, RuntimeFactory
from team import (
    LifecycleManager,
    MemberRegistry,
    MessageBus,
    TeamCoordinator,
    TeamRuntime,
)
from tools.task_system import TaskStore, create_task, list_tasks


class ExplodingRuntimeFactory:
    @staticmethod
    def create(**kwargs):
        raise AssertionError("TeamRuntime construction must not create AgentRuntime")


def test_team_runtime_composes_one_shared_instance_of_each_service(tmp_path):
    runtime = TeamRuntime(
        tmp_path / "tasks",
        runtime_factory=ExplodingRuntimeFactory,
    )

    assert isinstance(runtime.member_registry, MemberRegistry)
    assert isinstance(runtime.message_bus, MessageBus)
    assert isinstance(runtime.task_store, TaskStore)
    assert isinstance(runtime.lifecycle_manager, LifecycleManager)
    assert isinstance(runtime.coordinator, TeamCoordinator)
    assert runtime.task_store.directory == tmp_path / "tasks"
    assert runtime.lifecycle_manager.member_registry is runtime.member_registry
    assert runtime.lifecycle_manager.runtime_factory is ExplodingRuntimeFactory
    assert runtime.coordinator.member_registry is runtime.member_registry
    assert runtime.coordinator.message_bus is runtime.message_bus
    assert runtime.coordinator.task_store is runtime.task_store
    assert runtime.coordinator.lifecycle_manager is runtime.lifecycle_manager


def test_two_team_runtimes_do_not_share_mutable_state(tmp_path):
    first = TeamRuntime(tmp_path / "first" / "tasks")
    second = TeamRuntime(tmp_path / "second" / "tasks")

    first.member_registry.register("agent-1", "first")
    task = create_task("first task", "", store=first.task_store)

    assert first.member_registry is not second.member_registry
    assert first.message_bus is not second.message_bus
    assert first.task_store is not second.task_store
    assert first.lifecycle_manager is not second.lifecycle_manager
    assert first.coordinator is not second.coordinator
    assert second.member_registry.list() == ()
    assert [stored.id for stored in list_tasks(store=first.task_store)] == [task.id]
    assert list_tasks(store=second.task_store) == []


def test_team_runtime_is_independent_from_agent_runtime():
    assert not issubclass(TeamRuntime, AgentRuntime)
    assert RuntimeFactory is not TeamRuntime
