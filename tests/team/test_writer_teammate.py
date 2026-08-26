import pytest

from event import NullEventSink
from team.coordinator import TeamCoordinator, TeamError

from test_worktree import make_repo


def test_coordinator_binds_writer_to_worktree(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    lead = type(
        "Lead",
        (),
        {
            "session_id": "session",
            "agent_id": "lead-id",
            "paths": type(
                "Paths",
                (),
                {"workspace": repo, "state_root": repo},
            )(),
            "events": NullEventSink(),
            "state": type("State", (), {"turn_count": 0})(),
        },
    )()

    def runtime_factory(
        parent,
        coordinator,
        name,
        role,
        *,
        profile,
        workspace,
    ):
        return type(
            "Runtime",
            (),
            {
                "session_id": parent.session_id,
                "agent_id": f"{name}-id",
                "paths": type(
                    "Paths",
                    (),
                    {
                        "workspace": workspace or repo,
                        "state_root": repo,
                    },
                )(),
                "events": parent.events,
                "state": type(
                    "State",
                    (),
                    {"messages": [], "turn_count": 0},
                )(),
            },
        )()

    coordinator = TeamCoordinator(
        team_id="team_test",
        workspace=repo,
        runtime_factory=runtime_factory,
    )
    coordinator.bind_lead(lead)
    monkeypatch.setattr(
        "team.worker.run_turn",
        lambda runtime, prompt: (runtime.state, {"reason": "done"}),
    )

    member = coordinator.spawn(
        parent_runtime=lead,
        name="alice",
        role="implementer",
        prompt="implement",
        profile="writer",
    )

    handle = coordinator.member_worktrees["alice"]
    assert member.profile == "writer"
    assert member.branch == handle.branch
    assert coordinator.workers["alice"].runtime.paths.workspace == handle.path
    assert handle.path.is_dir()

    coordinator.shutdown_all()
    coordinator.worktrees.remove(handle)


def test_failed_writer_runtime_creation_rolls_back_branch(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    lead = type(
        "Lead",
        (),
        {
            "session_id": "session",
            "agent_id": "lead-id",
            "paths": type(
                "Paths",
                (),
                {"workspace": repo, "state_root": repo},
            )(),
            "events": NullEventSink(),
            "state": type("State", (), {"turn_count": 0})(),
        },
    )()

    def failing_factory(
        parent,
        coordinator,
        name,
        role,
        *,
        profile,
        workspace,
    ):
        raise RuntimeError("runtime factory failed")

    coordinator = TeamCoordinator(
        team_id="team_test",
        workspace=repo,
        runtime_factory=failing_factory,
    )
    coordinator.bind_lead(lead)

    with pytest.raises(RuntimeError, match="runtime factory failed"):
        coordinator.spawn(
            parent_runtime=lead,
            name="alice",
            role="implementer",
            prompt="implement",
            profile="writer",
        )

    def working_factory(
        parent,
        coordinator,
        name,
        role,
        *,
        profile,
        workspace,
    ):
        return type(
            "Runtime",
            (),
            {
                "session_id": parent.session_id,
                "agent_id": f"{name}-id",
                "paths": type(
                    "Paths",
                    (),
                    {"workspace": workspace, "state_root": repo},
                )(),
                "events": parent.events,
                "state": type(
                    "State",
                    (),
                    {"messages": [], "turn_count": 0},
                )(),
            },
        )()

    coordinator.runtime_factory = working_factory
    monkeypatch.setattr(
        "team.worker.run_turn",
        lambda runtime, prompt: (runtime.state, {"reason": "done"}),
    )

    coordinator.spawn(
        parent_runtime=lead,
        name="alice",
        role="implementer",
        prompt="implement",
        profile="writer",
    )

    handle = coordinator.member_worktrees["alice"]
    coordinator.shutdown_all()
    coordinator.worktrees.remove(handle, discard=True)


def test_writer_runtime_workspace_must_match_worktree(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    lead = type(
        "Lead",
        (),
        {
            "session_id": "session",
            "agent_id": "lead-id",
            "paths": type(
                "Paths",
                (),
                {"workspace": repo, "state_root": repo},
            )(),
            "events": NullEventSink(),
            "state": type("State", (), {"turn_count": 0})(),
        },
    )()

    def wrong_workspace_factory(
        parent,
        coordinator,
        name,
        role,
        *,
        profile,
        workspace,
    ):
        return type(
            "Runtime",
            (),
            {
                "session_id": parent.session_id,
                "agent_id": f"{name}-id",
                "paths": type(
                    "Paths",
                    (),
                    {"workspace": repo, "state_root": repo},
                )(),
                "events": parent.events,
                "state": type(
                    "State",
                    (),
                    {"messages": [], "turn_count": 0},
                )(),
            },
        )()

    coordinator = TeamCoordinator(
        team_id="team_test",
        workspace=repo,
        runtime_factory=wrong_workspace_factory,
    )
    coordinator.bind_lead(lead)

    with pytest.raises(TeamError, match="workspace"):
        coordinator.spawn(
            parent_runtime=lead,
            name="alice",
            role="implementer",
            prompt="implement",
            profile="writer",
        )

    assert "alice" not in coordinator.members
