from types import SimpleNamespace

from event import NullEventSink
from team.contract import TeammateProfile
from team.factory import create_teammate_runtime
from tools.task_system import TaskStore
from tools.team import TEAM_LEAD_TOOLS


def test_teammate_runtime_is_isolated_and_read_only(tmp_path):
    parent = SimpleNamespace(
        session_id="session",
        agent_id="lead-id",
        policy=SimpleNamespace(
            model={"api": "fake", "model_name": "primary"},
            fallback_model={"api": "fake", "model_name": "fallback"},
        ),
        state=SimpleNamespace(max_output_tokens=100),
        paths=SimpleNamespace(workspace=tmp_path),
        events=NullEventSink(),
    )
    coordinator = SimpleNamespace(tasks=TaskStore(tmp_path / "tasks"))
    coordinator.send = lambda *args, **kwargs: None
    coordinator.read_messages = lambda *args, **kwargs: []
    coordinator.snapshot = lambda: {}

    runtime = create_teammate_runtime(
        parent,
        coordinator,
        "alice",
        "reviewer",
    )
    tool_names = {tool["name"] for tool in runtime.policy.tools_list}

    assert runtime.session_id == parent.session_id
    assert runtime.agent_id != parent.agent_id
    assert runtime.state.messages == []
    assert runtime.memory.policy.can_read is True
    assert runtime.memory.policy.can_write is False
    assert runtime.policy.can_ask_user is False
    assert {
        "read_file",
        "glob",
        "load_skill",
        "list_tasks",
        "get_task",
        "claim_task",
        "complete_task",
        "send_message",
        "read_messages",
        "list_team",
    } <= tool_names
    assert {
        "bash",
        "write_file",
        "edit_file",
        "subagent",
        "spawn_teammate",
        "create_task",
        "update_task",
    }.isdisjoint(tool_names)


def test_writer_runtime_uses_worktree_and_shared_state_root(tmp_path):
    main_workspace = tmp_path / "main"
    writer_workspace = tmp_path / "writer"
    main_workspace.mkdir()
    writer_workspace.mkdir()
    parent = SimpleNamespace(
        session_id="session",
        agent_id="lead-id",
        policy=SimpleNamespace(
            model={"api": "fake", "model_name": "primary"},
            fallback_model={"api": "fake", "model_name": "fallback"},
        ),
        state=SimpleNamespace(max_output_tokens=100),
        paths=SimpleNamespace(workspace=main_workspace),
        events=NullEventSink(),
    )
    coordinator = SimpleNamespace(
        tasks=TaskStore(tmp_path / "tasks"),
        workspace=main_workspace,
    )
    coordinator.send = lambda *args, **kwargs: None
    coordinator.read_messages = lambda *args, **kwargs: []
    coordinator.snapshot = lambda *args, **kwargs: {}

    runtime = create_teammate_runtime(
        parent,
        coordinator,
        "alice",
        "implementer",
        profile=TeammateProfile.WRITER,
        workspace=writer_workspace,
    )
    tool_names = {tool["name"] for tool in runtime.policy.tools_list}

    assert runtime.paths.workspace == writer_workspace.resolve()
    assert runtime.paths.state_root == main_workspace.resolve()
    assert runtime.memory.root == main_workspace / ".agents" / ".memory" / "master"
    assert {"bash", "write_file", "edit_file"} <= tool_names
    assert {"subagent", "spawn_teammate", "create_task", "update_task"}.isdisjoint(
        tool_names
    )


def test_spawn_tool_description_matches_profile_capabilities():
    tool = next(item for item in TEAM_LEAD_TOOLS if item["name"] == "spawn_teammate")

    assert "researcher" in tool["description"]
    assert "writer" in tool["description"]
    assert "只读" in tool["description"]
    assert "独立 Git worktree" in tool["description"]
