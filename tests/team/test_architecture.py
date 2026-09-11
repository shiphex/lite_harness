from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_registry_does_not_import_runtime_factory():
    source = (PROJECT_ROOT / "team" / "registry.py").read_text(encoding="utf-8")

    assert "RuntimeFactory" not in source
    assert "core.runtime" not in source

def test_team_package_does_not_add_task_scheduler_or_worktree_modules():
    assert not (PROJECT_ROOT / "team" / "tasks.py").exists()
    assert not (PROJECT_ROOT / "team" / "scheduler.py").exists()
    assert not (PROJECT_ROOT / "team" / "worktree.py").exists()
