from event import NullEventSink
from team.coordinator import TeamCoordinator

from test_worktree import make_repo


def test_coordinator_binds_writer_to_worktree(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    lead = type(
        "Lead",
        (),
        {
            "session_id": "session",
            "agent_id": "lead-id",
            "paths": type("Paths", (), {"workspace": repo})(),
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
                "paths": type("Paths", (), {"workspace": workspace or repo})(),
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
