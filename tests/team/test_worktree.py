import subprocess

import pytest

from team.worktree import WorktreeError, WorktreeManager


def git(cwd, *args):
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "tests@example.invalid")
    git(repo, "config", "user.name", "tests")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "initial")
    return repo


def test_worktree_manager_creates_status_and_explicitly_removes(tmp_path):
    repo = make_repo(tmp_path)
    manager = WorktreeManager(repo_root=repo, team_id="team_test")

    handle = manager.create(member="alice")

    assert handle.path.is_dir()
    assert handle.branch == "agent/team_test/alice"
    assert manager.status(handle) == ""
    assert git(handle.path, "branch", "--show-current") == handle.branch

    (handle.path / "README.md").write_text("changed\n", encoding="utf-8")
    with pytest.raises(WorktreeError):
        manager.remove(handle)

    manager.remove(handle, discard=True)
    assert not handle.path.exists()


def test_worktree_manager_rejects_dirty_lead_workspace(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "README.md").write_text("dirty\n", encoding="utf-8")
    manager = WorktreeManager(repo_root=repo, team_id="team_test")

    with pytest.raises(WorktreeError, match="没有未提交修改"):
        manager.create(member="alice")


def test_worktree_manager_removes_clean_locked_worktree(tmp_path):
    repo = make_repo(tmp_path)
    manager = WorktreeManager(repo_root=repo, team_id="team_test")

    handle = manager.create(member="alice")
    manager.remove(handle)

    assert not handle.path.exists()
