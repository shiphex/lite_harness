from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_registry_does_not_import_runtime_factory():
    source = (PROJECT_ROOT / "team" / "registry.py").read_text(encoding="utf-8")

    assert "RuntimeFactory" not in source
    assert "core.runtime" not in source

def test_team_package_does_not_add_task_scheduler_or_worktree_modules():
    assert not (PROJECT_ROOT / "team" / "scheduler.py").exists()
    assert not (PROJECT_ROOT / "team" / "worktree.py").exists()


def test_teamagent_creation_entrypoint_is_lifecycle_manager():
    lifecycle = (PROJECT_ROOT / "team" / "lifecycle.py").read_text(
        encoding="utf-8"
    )
    coordinator = (PROJECT_ROOT / "team" / "coordinator.py").read_text(
        encoding="utf-8"
    )
    agent = (PROJECT_ROOT / "team" / "agent.py").read_text(encoding="utf-8")
    team_tool = (PROJECT_ROOT / "tools" / "team.py").read_text(encoding="utf-8")

    assert "self.runtime_factory.create(" in lifecycle
    for source in (coordinator, agent, team_tool):
        assert "RuntimeFactory" not in source
        assert "runtime_factory.create(" not in source


def test_teamagent_uses_existing_query_loop_without_new_runtime_type():
    agent = (PROJECT_ROOT / "team" / "agent.py").read_text(encoding="utf-8")

    assert "from core.loop import query_loop" in agent
    assert "AgentRuntime" in agent
    assert "TeamAgentRuntime" not in agent
