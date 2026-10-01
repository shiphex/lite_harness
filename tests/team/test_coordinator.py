from types import SimpleNamespace

from team.coordinator import TeamCoordinator


def test_spawn_teammate_delegates_to_lifecycle_manager():
    calls = []
    expected = object()
    lifecycle = SimpleNamespace(
        spawn=lambda **kwargs: calls.append(kwargs) or expected
    )
    coordinator = TeamCoordinator(
        member_registry=object(),
        message_bus=object(),
        task_store=object(),
        lifecycle_manager=lifecycle,
    )
    parent_runtime = object()

    result = coordinator.spawn_teammate(
        parent_runtime=parent_runtime,
        agent_name="researcher",
    )

    assert result is expected
    assert calls == [
        {
            "parent_runtime": parent_runtime,
            "agent_name": "researcher",
        }
    ]
