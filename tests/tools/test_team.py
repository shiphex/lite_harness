import json
from types import SimpleNamespace

from team.contracts import MemberRecord, MemberState, SpawnError
from team.runtime import TeamRuntime
from tools.team import TEAM_MASTER_TOOLS, bind_team_handlers
from tools.tool_class import ToolContext
from tools.tool_handler import STANDARD_TOOLS_LIST


def test_spawn_tool_schema_and_standard_tool_exclusion():
    tool = TEAM_MASTER_TOOLS[0]

    assert tool["name"] == "spawn_teammate"
    assert tool["input_schema"]["required"] == ["agent_name"]
    assert "spawn_teammate" not in {
        definition["name"] for definition in STANDARD_TOOLS_LIST
    }


def test_bound_spawn_handler_uses_calling_master_runtime():
    calls = []
    coordinator = SimpleNamespace(
        spawn_teammate=lambda **kwargs: calls.append(kwargs)
        or MemberRecord(
            agent_id="researcher-id",
            agent_name="researcher",
            state=MemberState.IDLE,
        )
    )
    team_runtime = SimpleNamespace(coordinator=coordinator)
    handler = bind_team_handlers(team_runtime)["spawn_teammate"]
    master_runtime = object()

    result = json.loads(
        handler(ToolContext(master_runtime), agent_name="researcher")
    )

    assert calls == [
        {
            "parent_runtime": master_runtime,
            "agent_name": "researcher",
        }
    ]
    assert result == {
        "agent_id": "researcher-id",
        "agent_name": "researcher",
        "state": "idle",
    }


def test_bound_spawn_handler_returns_typed_domain_failure():
    def fail(**kwargs):
        raise SpawnError("cannot spawn")

    team_runtime = SimpleNamespace(
        coordinator=SimpleNamespace(spawn_teammate=fail)
    )
    handler = bind_team_handlers(team_runtime)["spawn_teammate"]

    assert handler(ToolContext(object()), agent_name="researcher") == (
        "Team error: cannot spawn"
    )


def test_spawn_tool_runs_complete_vertical_slice_with_fake_runtime(
    tmp_path,
):
    calls = []

    class FakeRuntimeFactory:
        @staticmethod
        def create(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                agent_id="runtime-agent-id",
                agent_name=kwargs["agent_name"],
                session_id=kwargs["session_id"],
                policy=kwargs["policy"],
                state=kwargs["state"],
                paths=SimpleNamespace(workspace=kwargs["workspace"]),
            )

    team_runtime = TeamRuntime(
        tmp_path / ".agents" / "runs" / "session-1" / "tasks",
        session_id="session-1",
        runtime_factory=FakeRuntimeFactory,
    )
    parent_runtime = SimpleNamespace(
        session_id="session-1",
        policy=SimpleNamespace(
            model={"api": "fake", "model_name": "primary"},
            fallback_model={"api": "fake", "model_name": "fallback"},
        ),
        state=SimpleNamespace(max_output_tokens=1024),
        paths=SimpleNamespace(workspace=tmp_path),
    )
    handler = bind_team_handlers(team_runtime)["spawn_teammate"]

    result = json.loads(
        handler(ToolContext(parent_runtime), agent_name="researcher")
    )

    assert len(calls) == 1
    assert result == {
        "agent_id": "runtime-agent-id",
        "agent_name": "researcher",
        "state": "idle",
    }
    assert team_runtime.member_registry.get("runtime-agent-id").state is (
        MemberState.IDLE
    )
    assert set(team_runtime.lifecycle_manager._agents) == {"runtime-agent-id"}
