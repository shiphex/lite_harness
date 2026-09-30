"""Phase 6: accepted team boundaries working together without a real model."""

import json
from types import SimpleNamespace

from core.runtime import RuntimeFactory
from team.agent import TeamAgent
from team.contracts import MemberState
from team.runtime import TeamRuntime
from tools.task_system import load_task
from tools.team import bind_team_handlers
from tools.tool_class import ToolContext


def _team(tmp_path, loop):
    team = TeamRuntime(
        tmp_path / "tasks",
        session_id="phase-six-session",
        runtime_factory=RuntimeFactory,
        agent_factory=lambda **kwargs: TeamAgent(run_loop=loop, **kwargs),
    )
    master = SimpleNamespace(
        session_id="phase-six-session",
        policy=SimpleNamespace(
            model={"api": "fake", "model_name": "primary"},
            fallback_model={"api": "fake", "model_name": "fallback"},
        ),
        state=SimpleNamespace(max_output_tokens=1024),
        paths=SimpleNamespace(workspace=tmp_path),
    )
    return team, master, bind_team_handlers(team)


def _tool(handlers, name, master, **arguments):
    result = handlers[name](ToolContext(master), **arguments)
    assert not result.startswith("Team error"), result
    return json.loads(result)


def test_master_bound_team_workflow_connects_messages_tasks_and_release(tmp_path):
    def complete_in_fake_loop(runtime):
        task_id = json.loads(runtime.state.messages[-1]["content"])["task_id"]
        completed = runtime.tools.execute(
            ToolContext(runtime), "complete_team_task", {"task_id": task_id}
        )
        assert json.loads(completed)["status"] == "completed"
        return runtime.state, {"reason": "completed"}

    team, master, handlers = _team(tmp_path, complete_in_fake_loop)
    sender = _tool(handlers, "spawn_teammate", master, agent_name="sender")
    worker = _tool(handlers, "spawn_teammate", master, agent_name="worker")
    sender_id, worker_id = sender["agent_id"], worker["agent_id"]
    sender_runtime = team.lifecycle_manager.get_agent(sender_id).runtime
    worker_runtime = team.lifecycle_manager.get_agent(worker_id).runtime

    assert sender_id != worker_id
    assert sender_runtime.session_id == worker_runtime.session_id == master.session_id
    assert sender_runtime.state is not worker_runtime.state
    assert sender_runtime.paths.agent_dir != worker_runtime.paths.agent_dir

    sent = sender_runtime.tools.execute(
        ToolContext(sender_runtime),
        "send_team_message",
        {"target_id": worker_id, "content": "Please handle the task"},
    )
    received = worker_runtime.tools.execute(
        ToolContext(worker_runtime), "receive_team_message", {}
    )
    assert json.loads(sent) == {"status": "sent"}
    assert json.loads(received)["message"] == {
        "sender_id": sender_id,
        "target_id": worker_id,
        "content": "Please handle the task",
    }
    assert sender_runtime.state.messages == worker_runtime.state.messages == []

    task = _tool(
        handlers, "create_team_task", master,
        subject="integrated task", description="complete via TeamAgent",
    )["task"]
    assigned = _tool(
        handlers, "assign_team_task", master,
        task_id=task["id"], agent_id=worker_id,
    )

    assert assigned["status"] == "completed"
    assert assigned["member_state"] == "idle"
    assert load_task(task["id"], store=team.task_store).owner == worker_id
    assert load_task(task["id"], store=team.task_store).status == "completed"
    assert team.member_registry.get(worker_id).state is MemberState.IDLE

    released = _tool(handlers, "teardown_team", master)
    assert released["released"] is True
    assert released["failures"] == {}
    assert team.member_registry.list() == ()
    assert load_task(task["id"], store=team.task_store).status == "completed"


def test_fatal_task_recovery_preserves_owner_until_new_member_completes(tmp_path):
    def complete_only_after_recovery(runtime):
        if runtime.agent_name.startswith("recovery_"):
            task_id = json.loads(runtime.state.messages[-1]["content"])["task_id"]
            completed = runtime.tools.execute(
                ToolContext(runtime), "complete_team_task", {"task_id": task_id}
            )
            assert json.loads(completed)["status"] == "completed"
        return runtime.state, {"reason": "completed"}

    team, master, handlers = _team(tmp_path, complete_only_after_recovery)
    original_id = _tool(handlers, "spawn_teammate", master, agent_name="original")["agent_id"]
    task_id = _tool(
        handlers, "create_team_task", master,
        subject="recover task", description="continue safely",
    )["task"]["id"]
    assigned = _tool(
        handlers, "assign_team_task", master,
        task_id=task_id, agent_id=original_id,
    )
    assert assigned["status"] == "in_progress"
    assert load_task(task_id, store=team.task_store).owner == original_id

    fatal = _tool(
        handlers, "report_team_fatal", master,
        agent_id=original_id, error="runtime corrupted",
    )
    first_close = _tool(handlers, "teardown_team", master)
    assert fatal["member_state"] == "failed"
    assert fatal["task_ids"] == [task_id]
    assert first_close["released"] is False
    assert first_close["failures"][original_id]["type"] == "StopPendingTaskError"
    assert team.member_registry.get(original_id).state is MemberState.FAILED
    assert load_task(task_id, store=team.task_store).owner == original_id

    recovered = _tool(
        handlers, "recover_failed_team_task", master, task_id=task_id
    )
    successor_id = recovered["agent_id"]
    saved = load_task(task_id, store=team.task_store)
    assert successor_id != original_id
    assert recovered["status"] == "completed"
    assert recovered["previous_owner"] == original_id
    assert saved.id == task_id
    assert saved.status == "completed"
    assert saved.owner == successor_id
    assert saved.reassignments == [{
        "from_owner": original_id,
        "to_owner": successor_id,
        "reason": "source_failed",
    }]
    assert team.member_registry.get(original_id).state is MemberState.FAILED

    released = _tool(handlers, "teardown_team", master)
    assert released["released"] is True
    assert team.member_registry.list() == ()
    assert load_task(task_id, store=team.task_store).owner == successor_id
