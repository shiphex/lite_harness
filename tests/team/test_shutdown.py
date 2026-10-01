import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace

import pytest

from core.runtime import RuntimeFactory
from team.agent import TeamAgent
from team.contracts import MemberEvent, MemberState, MessageUnavailableError, TransitionSource
from team.runtime import TeamRuntime
from tools.task_system import claim_task_strict, create_task, load_task
from tools.team import bind_team_handlers
from tools.tool_class import ToolContext


def make_team(tmp_path, loop=None, session_id="session-1"):
    if loop is None:
        loop = lambda runtime: (runtime.state, {"reason": "completed"})
    team = TeamRuntime(
        tmp_path / session_id / "tasks",
        session_id=session_id,
        runtime_factory=RuntimeFactory,
        agent_factory=lambda **kwargs: TeamAgent(run_loop=loop, **kwargs),
    )
    master = SimpleNamespace(
        session_id=session_id,
        policy=SimpleNamespace(
            model={"api": "fake", "model_name": "primary"},
            fallback_model={"api": "fake", "model_name": "fallback"},
        ),
        state=SimpleNamespace(max_output_tokens=1024),
        paths=SimpleNamespace(workspace=tmp_path),
    )
    return team, master, bind_team_handlers(team)


def test_master_shutdown_stops_idle_member_and_is_idempotent(tmp_path):
    team, master, handlers = make_team(tmp_path)
    member = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    original = team.lifecycle_manager.get_agent(member.agent_id)

    first = json.loads(handlers["shutdown_teammate"](ToolContext(master), agent_id=member.agent_id))

    assert first["status"] == "stopped"
    assert first["member_state"] == "stopped"
    assert team.member_registry.get(member.agent_id).state is MemberState.STOPPED
    with pytest.raises(MessageUnavailableError):
        team.lifecycle_manager.get_agent(member.agent_id)
    with pytest.raises(MessageUnavailableError):
        original.mailbox_handle.receive()

    second = json.loads(handlers["shutdown_teammate"](ToolContext(master), agent_id=member.agent_id))
    assert second == first


def test_shutdown_preserves_unfinished_task_until_owner_resumes(tmp_path):
    calls = []

    def loop(runtime):
        calls.append(runtime.agent_id)
        if len(calls) == 1:
            return runtime.state, {"reason": "max_turns"}
        task_id = json.loads(runtime.state.messages[-1]["content"])["task_id"]
        result = runtime.tools.execute(
            ToolContext(runtime), "complete_team_task", {"task_id": task_id}
        )
        assert json.loads(result)["status"] == "completed"
        return runtime.state, {"reason": "completed"}

    team, master, handlers = make_team(tmp_path, loop)
    member = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    task = create_task("work", "", store=team.task_store)
    handlers["assign_team_task"](ToolContext(master), task_id=task.id, agent_id=member.agent_id)

    rejected = handlers["shutdown_teammate"](ToolContext(master), agent_id=member.agent_id)
    assert "StopPendingTaskError" in rejected
    assert team.member_registry.get(member.agent_id).state is MemberState.BUSY
    assert team.lifecycle_manager.get_agent(member.agent_id).runtime.agent_id == member.agent_id
    assert load_task(task.id, store=team.task_store).status == "in_progress"

    handlers["resume_team_task"](ToolContext(master), task_id=task.id, agent_id=member.agent_id)
    stopped = json.loads(handlers["shutdown_teammate"](ToolContext(master), agent_id=member.agent_id))
    assert stopped["status"] == "stopped"
    assert load_task(task.id, store=team.task_store).status == "completed"


def test_shutdown_does_not_interrupt_active_synchronous_turn(tmp_path):
    entered = Event()
    release = Event()

    def loop(runtime):
        entered.set()
        assert release.wait(5)
        return runtime.state, {"reason": "max_turns"}

    team, master, handlers = make_team(tmp_path, loop)
    member = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    task = create_task("work", "", store=team.task_store)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(team.coordinator.assign_task, task.id, member.agent_id)
        assert entered.wait(5)
        try:
            rejected = handlers["shutdown_teammate"](ToolContext(master), agent_id=member.agent_id)
            assert "StopBusyError" in rejected
            assert team.member_registry.get(member.agent_id).state is MemberState.BUSY
        finally:
            release.set()
        assert future.result(timeout=5)["status"] == "in_progress"


def test_waiting_member_cannot_be_stopped_or_lose_its_task(tmp_path):
    team, master, handlers = make_team(tmp_path)
    member = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    task = create_task("work", "", store=team.task_store)
    handlers["assign_team_task"](ToolContext(master), task_id=task.id, agent_id=member.agent_id)
    team.member_registry.transition(
        member.agent_id, MemberEvent.DEPENDENCY_WAIT, source=TransitionSource.TEAM_AGENT
    )

    assert "StopPendingTaskError" in handlers["shutdown_teammate"](ToolContext(master), agent_id=member.agent_id)
    assert team.member_registry.get(member.agent_id).state is MemberState.WAITING
    assert load_task(task.id, store=team.task_store).owner == member.agent_id
    assert team.lifecycle_manager.get_agent(member.agent_id).runtime.agent_id == member.agent_id


def test_teardown_aggregates_failures_and_retries_after_owner_recovers(tmp_path):
    def loop(runtime):
        task_id = json.loads(runtime.state.messages[-1]["content"])["task_id"]
        if runtime.state.context.get("finish"):
            runtime.tools.execute(ToolContext(runtime), "complete_team_task", {"task_id": task_id})
        return runtime.state, {"reason": "completed"}

    team, master, handlers = make_team(tmp_path, loop)
    idle = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="idle")
    busy = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="busy")
    task = create_task("work", "", store=team.task_store)
    handlers["assign_team_task"](ToolContext(master), task_id=task.id, agent_id=busy.agent_id)

    first = json.loads(handlers["teardown_team"](ToolContext(master)))
    assert first["status"] == "partial"
    assert first["released"] is False
    assert first["stopped"] == [idle.agent_id]
    assert first["failures"][busy.agent_id]["type"] == "StopPendingTaskError"
    assert team.member_registry.get(idle.agent_id).state is MemberState.STOPPED
    assert team.lifecycle_manager.get_agent(busy.agent_id).runtime.agent_id == busy.agent_id

    team.lifecycle_manager.get_agent(busy.agent_id).runtime.state.context["finish"] = True
    handlers["resume_team_task"](ToolContext(master), task_id=task.id, agent_id=busy.agent_id)
    second = json.loads(handlers["teardown_team"](ToolContext(master)))
    assert second["status"] == "released"
    assert second["released"] is True
    assert second["failures"] == {}
    assert team.member_registry.list() == ()
    assert load_task(task.id, store=team.task_store).status == "completed"
    assert json.loads(handlers["teardown_team"](ToolContext(master))) == second


def test_fatal_is_explicit_and_keeps_error_and_task_facts(tmp_path):
    def broken_loop(runtime):
        raise RuntimeError("recoverable model failure")

    team, master, handlers = make_team(tmp_path, broken_loop)
    member = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    task = create_task("work", "", store=team.task_store)
    result = json.loads(handlers["assign_team_task"](ToolContext(master), task_id=task.id, agent_id=member.agent_id))
    assert result["status"] == "execution_error"
    assert team.member_registry.get(member.agent_id).state is MemberState.BUSY

    fatal = json.loads(handlers["report_team_fatal"](ToolContext(master), agent_id=member.agent_id, error="runtime corrupted"))
    assert fatal["member_state"] == "failed"
    assert fatal["error"] == "runtime corrupted"
    assert fatal["task_ids"] == [task.id]
    assert team.member_registry.get(member.agent_id).state is MemberState.FAILED
    assert load_task(task.id, store=team.task_store).owner == member.agent_id
    assert load_task(task.id, store=team.task_store).status == "in_progress"
    queried = json.loads(handlers["get_team_member"](ToolContext(master), agent_id=member.agent_id))
    assert queried["member_state"] == "failed"
    assert queried["error"] == "runtime corrupted"
    assert queried["task_ids"] == [task.id]
    close = json.loads(handlers["teardown_team"](ToolContext(master)))
    assert close["status"] == "partial"
    assert close["failures"][member.agent_id]["type"] == "StopPendingTaskError"
    assert team.member_registry.get(member.agent_id).state is MemberState.FAILED


def test_master_recovers_failed_task_with_new_agent_without_using_idle_member(tmp_path):
    turns = []

    def loop(runtime):
        turns.append(runtime.agent_id)
        if runtime.agent_name.startswith("recovery_"):
            task_id = json.loads(runtime.state.messages[-1]["content"])["task_id"]
            result = runtime.tools.execute(
                ToolContext(runtime), "complete_team_task", {"task_id": task_id}
            )
            assert json.loads(result)["status"] == "completed"
        return runtime.state, {"reason": "completed"}

    team, master, handlers = make_team(tmp_path, loop)
    failed = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="failed")
    idle = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="idle")
    failed_runtime = team.lifecycle_manager.get_agent(failed.agent_id).runtime
    idle_runtime = team.lifecycle_manager.get_agent(idle.agent_id).runtime
    task = create_task("work", "", store=team.task_store)
    handlers["assign_team_task"](ToolContext(master), task_id=task.id, agent_id=failed.agent_id)
    handlers["report_team_fatal"](ToolContext(master), agent_id=failed.agent_id, error="corrupt")

    recovered = json.loads(handlers["recover_failed_team_task"](ToolContext(master), task_id=task.id))

    new_id = recovered["agent_id"]
    assert recovered["status"] == "completed"
    assert recovered["previous_owner"] == failed.agent_id
    assert new_id not in {failed.agent_id, idle.agent_id}
    assert team.member_registry.get(new_id).agent_name == f"recovery_{task.id}"
    assert team.member_registry.get(idle.agent_id).state is MemberState.IDLE
    assert idle_runtime.state.messages == []
    new_runtime = team.lifecycle_manager.get_agent(new_id).runtime
    assert new_runtime.state is not failed_runtime.state
    assert new_runtime.paths.agent_dir != failed_runtime.paths.agent_dir
    assert len(new_runtime.state.messages) == 1
    assert turns == [failed.agent_id, new_id]
    saved = load_task(task.id, store=team.task_store)
    assert saved.status == "completed"
    assert saved.owner == new_id
    assert saved.reassignments == [{
        "from_owner": failed.agent_id,
        "to_owner": new_id,
        "reason": "source_failed",
    }]
    assert team.member_registry.get(failed.agent_id).state is MemberState.FAILED
    assert json.loads(handlers["teardown_team"](ToolContext(master)))["released"] is True


def test_recovery_rejects_recoverable_owner_without_spawning(tmp_path):
    team, master, handlers = make_team(tmp_path)
    member = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    task = create_task("work", "", store=team.task_store)
    handlers["assign_team_task"](ToolContext(master), task_id=task.id, agent_id=member.agent_id)
    before = team.member_registry.list()

    result = handlers["recover_failed_team_task"](ToolContext(master), task_id=task.id)

    assert "TeamError" in result
    assert team.member_registry.list() == before
    assert load_task(task.id, store=team.task_store).owner == member.agent_id
    foreign_task = create_task("foreign", "", store=team.task_store)
    claim_task_strict(foreign_task.id, "outside-team", store=team.task_store)
    assert "MemberNotFoundError" in handlers["recover_failed_team_task"](
        ToolContext(master), task_id=foreign_task.id
    )
    assert team.member_registry.list() == before


def test_recovery_rejects_pending_and_completed_tasks(tmp_path):
    def loop(runtime):
        task_id = json.loads(runtime.state.messages[-1]["content"])["task_id"]
        runtime.tools.execute(ToolContext(runtime), "complete_team_task", {"task_id": task_id})
        return runtime.state, {"reason": "completed"}

    team, master, handlers = make_team(tmp_path, loop)
    member = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    pending = create_task("pending", "", store=team.task_store)
    completed = create_task("completed", "", store=team.task_store)
    handlers["assign_team_task"](
        ToolContext(master), task_id=completed.id, agent_id=member.agent_id
    )
    handlers["report_team_fatal"](
        ToolContext(master), agent_id=member.agent_id, error="fatal"
    )
    before = team.member_registry.list()

    for task in (pending, completed):
        assert "TeamError" in handlers["recover_failed_team_task"](
            ToolContext(master), task_id=task.id
        )
    assert team.member_registry.list() == before
    assert load_task(completed.id, store=team.task_store).reassignments == []


def test_recovery_loads_legacy_task_and_new_owner_can_resume(tmp_path):
    def loop(runtime):
        if runtime.agent_name.startswith("recovery_") and runtime.state.context.get("finish"):
            task_id = json.loads(runtime.state.messages[-1]["content"])["task_id"]
            runtime.tools.execute(ToolContext(runtime), "complete_team_task", {"task_id": task_id})
        return runtime.state, {"reason": "max_turns"}

    team, master, handlers = make_team(tmp_path, loop)
    failed = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    task = create_task("work", "", store=team.task_store)
    handlers["assign_team_task"](ToolContext(master), task_id=task.id, agent_id=failed.agent_id)
    handlers["report_team_fatal"](ToolContext(master), agent_id=failed.agent_id, error="fatal")
    path = team.task_store._path(task.id)
    legacy = json.loads(path.read_text(encoding="utf-8"))
    legacy.pop("reassignments", None)
    path.write_text(json.dumps(legacy), encoding="utf-8")

    first = json.loads(handlers["recover_failed_team_task"](ToolContext(master), task_id=task.id))
    assert first["status"] == "in_progress"
    assert load_task(task.id, store=team.task_store).reassignments[0]["from_owner"] == failed.agent_id
    assert json.loads(handlers["teardown_team"](ToolContext(master)))["released"] is False
    team.lifecycle_manager.get_agent(first["agent_id"]).runtime.state.context["finish"] = True
    resumed = json.loads(handlers["resume_team_task"](
        ToolContext(master), task_id=task.id, agent_id=first["agent_id"]
    ))
    assert resumed["status"] == "completed"
    assert json.loads(handlers["teardown_team"](ToolContext(master)))["released"] is True


def test_recovery_spawn_failure_keeps_old_owner_and_no_new_member(tmp_path, monkeypatch):
    team, master, handlers = make_team(tmp_path)
    failed = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    task = create_task("work", "", store=team.task_store)
    handlers["assign_team_task"](ToolContext(master), task_id=task.id, agent_id=failed.agent_id)
    handlers["report_team_fatal"](ToolContext(master), agent_id=failed.agent_id, error="fatal")
    monkeypatch.setattr(team.lifecycle_manager, "agent_factory", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("spawn failed")))

    result = handlers["recover_failed_team_task"](ToolContext(master), task_id=task.id)

    assert "SpawnError" in result
    assert [member.agent_id for member in team.member_registry.list()] == [failed.agent_id]
    saved = load_task(task.id, store=team.task_store)
    assert saved.owner == failed.agent_id
    assert saved.reassignments == []


def test_recovery_write_failure_stops_new_member_and_preserves_old_task(tmp_path, monkeypatch):
    import tools.task_system as task_system

    team, master, handlers = make_team(tmp_path)
    failed = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    task = create_task("work", "", store=team.task_store)
    handlers["assign_team_task"](ToolContext(master), task_id=task.id, agent_id=failed.agent_id)
    handlers["report_team_fatal"](ToolContext(master), agent_id=failed.agent_id, error="fatal")
    monkeypatch.setattr(task_system.os, "replace", lambda *args: (_ for _ in ()).throw(OSError("disk error")))

    result = handlers["recover_failed_team_task"](ToolContext(master), task_id=task.id)

    assert "TaskError" in result
    saved = load_task(task.id, store=team.task_store)
    assert saved.owner == failed.agent_id
    assert saved.reassignments == []
    assert [member.state for member in team.member_registry.list()] == [MemberState.FAILED, MemberState.STOPPED]
    assert list(team.task_store.directory.glob("*.tmp")) == []


def test_recovery_tempfile_failure_reports_error_and_preserves_owner(tmp_path, monkeypatch):
    import tools.task_system as task_system

    team, master, handlers = make_team(tmp_path)
    failed = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    task = create_task("work", "", store=team.task_store)
    handlers["assign_team_task"](ToolContext(master), task_id=task.id, agent_id=failed.agent_id)
    handlers["report_team_fatal"](ToolContext(master), agent_id=failed.agent_id, error="fatal")
    monkeypatch.setattr(task_system.tempfile, "mkstemp", lambda **kwargs: (_ for _ in ()).throw(OSError("no temp")))

    result = handlers["recover_failed_team_task"](ToolContext(master), task_id=task.id)

    assert "TaskError" in result
    assert load_task(task.id, store=team.task_store).owner == failed.agent_id
    assert [member.state for member in team.member_registry.list()] == [MemberState.FAILED, MemberState.STOPPED]


def test_recovery_transition_failure_keeps_new_owner_resumable(tmp_path, monkeypatch):
    def loop(runtime):
        if runtime.agent_name.startswith("recovery_"):
            task_id = json.loads(runtime.state.messages[-1]["content"])["task_id"]
            runtime.tools.execute(ToolContext(runtime), "complete_team_task", {"task_id": task_id})
        return runtime.state, {"reason": "completed"}

    team, master, handlers = make_team(tmp_path, loop)
    failed = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    task = create_task("work", "", store=team.task_store)
    handlers["assign_team_task"](ToolContext(master), task_id=task.id, agent_id=failed.agent_id)
    handlers["report_team_fatal"](ToolContext(master), agent_id=failed.agent_id, error="fatal")
    original = team.member_registry.transition

    def fail_claim(agent_id, event, *, source):
        if event is MemberEvent.TASK_CLAIMED and agent_id != failed.agent_id:
            raise RuntimeError("registry error")
        return original(agent_id, event, source=source)

    monkeypatch.setattr(team.member_registry, "transition", fail_claim)
    result = json.loads(handlers["recover_failed_team_task"](ToolContext(master), task_id=task.id))
    assert result["status"] == "inconsistent"
    assert "registry error" in result["error"]
    assert load_task(task.id, store=team.task_store).owner == result["agent_id"]
    assert team.member_registry.get(result["agent_id"]).state is MemberState.IDLE

    monkeypatch.setattr(team.member_registry, "transition", original)
    resumed = json.loads(handlers["resume_team_task"](
        ToolContext(master), task_id=task.id, agent_id=result["agent_id"]
    ))
    assert resumed["status"] == "completed"


def test_recovery_can_repeat_after_new_member_fails(tmp_path):
    recovery_ids = []

    def loop(runtime):
        if runtime.agent_name.startswith("recovery_"):
            recovery_ids.append(runtime.agent_id)
            if len(recovery_ids) == 2:
                task_id = json.loads(runtime.state.messages[-1]["content"])["task_id"]
                runtime.tools.execute(ToolContext(runtime), "complete_team_task", {"task_id": task_id})
        return runtime.state, {"reason": "completed"}

    team, master, handlers = make_team(tmp_path, loop)
    failed = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    task = create_task("work", "", store=team.task_store)
    handlers["assign_team_task"](ToolContext(master), task_id=task.id, agent_id=failed.agent_id)
    handlers["report_team_fatal"](ToolContext(master), agent_id=failed.agent_id, error="fatal")

    first = json.loads(handlers["recover_failed_team_task"](ToolContext(master), task_id=task.id))
    assert first["status"] == "in_progress"
    handlers["report_team_fatal"](ToolContext(master), agent_id=first["agent_id"], error="fatal again")
    second = json.loads(handlers["recover_failed_team_task"](ToolContext(master), task_id=task.id))

    assert second["status"] == "completed"
    assert second["agent_id"] != first["agent_id"]
    assert load_task(task.id, store=team.task_store).reassignments == [
        {"from_owner": failed.agent_id, "to_owner": first["agent_id"], "reason": "source_failed"},
        {"from_owner": first["agent_id"], "to_owner": second["agent_id"], "reason": "source_failed"},
    ]
    assert json.loads(handlers["teardown_team"](ToolContext(master)))["released"] is True


def test_two_concurrent_recovery_requests_create_one_successor(tmp_path):
    team, master, handlers = make_team(tmp_path)
    failed = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    task = create_task("work", "", store=team.task_store)
    handlers["assign_team_task"](ToolContext(master), task_id=task.id, agent_id=failed.agent_id)
    handlers["report_team_fatal"](ToolContext(master), agent_id=failed.agent_id, error="fatal")

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(
            lambda _: handlers["recover_failed_team_task"](ToolContext(master), task_id=task.id),
            range(2),
        ))

    successes = [json.loads(value) for value in results if value.startswith("{")]
    assert len(successes) == 1
    assert sum("Team error" in value for value in results) == 1
    assert len(team.member_registry.list()) == 2
    assert load_task(task.id, store=team.task_store).owner == successes[0]["agent_id"]


def test_recovery_handles_failed_member_tasks_one_at_a_time(tmp_path):
    def loop(runtime):
        if runtime.agent_name.startswith("recovery_"):
            task_id = json.loads(runtime.state.messages[-1]["content"])["task_id"]
            runtime.tools.execute(ToolContext(runtime), "complete_team_task", {"task_id": task_id})
        return runtime.state, {"reason": "completed"}

    team, master, handlers = make_team(tmp_path, loop)
    failed = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    first = create_task("first", "", store=team.task_store)
    second = create_task("second", "", store=team.task_store)
    handlers["assign_team_task"](ToolContext(master), task_id=first.id, agent_id=failed.agent_id)
    claim_task_strict(second.id, failed.agent_id, store=team.task_store)
    handlers["report_team_fatal"](ToolContext(master), agent_id=failed.agent_id, error="fatal")

    handlers["recover_failed_team_task"](ToolContext(master), task_id=first.id)
    assert json.loads(handlers["teardown_team"](ToolContext(master)))["released"] is False
    handlers["recover_failed_team_task"](ToolContext(master), task_id=second.id)
    assert json.loads(handlers["teardown_team"](ToolContext(master)))["released"] is True


def test_teardown_reports_failed_member_separately_from_stopped(tmp_path):
    team, master, handlers = make_team(tmp_path)
    member = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    handlers["report_team_fatal"](ToolContext(master), agent_id=member.agent_id, error="runtime corrupted")

    result = json.loads(handlers["teardown_team"](ToolContext(master)))
    assert result["released"] is True
    assert result["stopped"] == []
    assert result["failed"] == [member.agent_id]


def test_shutdown_orders_with_message_send_and_preserves_mailbox_until_release(tmp_path):
    team, master, handlers = make_team(tmp_path)
    sender = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="sender")
    target = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="target")
    sender_handle = team.lifecycle_manager.get_agent(sender.agent_id).mailbox_handle
    target_handle = team.lifecycle_manager.get_agent(target.agent_id).mailbox_handle
    sender_handle.send(target.agent_id, "accepted")

    stopped = json.loads(handlers["shutdown_teammate"](ToolContext(master), agent_id=target.agent_id))
    assert stopped["member_state"] == "stopped"
    assert len(team.message_bus._mailboxes[target.agent_id]) == 1
    with pytest.raises(MessageUnavailableError):
        sender_handle.send(target.agent_id, "late")
    with pytest.raises(MessageUnavailableError):
        target_handle.receive()
    assert len(team.message_bus._mailboxes[target.agent_id]) == 1
    assert json.loads(handlers["teardown_team"](ToolContext(master)))["released"] is True
    assert team.message_bus._mailboxes == {}


def test_completed_task_with_failed_member_finish_must_be_repaired_before_stop(tmp_path, monkeypatch):
    def loop(runtime):
        task_id = json.loads(runtime.state.messages[-1]["content"])["task_id"]
        runtime.tools.execute(ToolContext(runtime), "complete_team_task", {"task_id": task_id})
        return runtime.state, {"reason": "completed"}

    team, master, handlers = make_team(tmp_path, loop)
    member = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    task = create_task("work", "", store=team.task_store)
    original = team.member_registry.transition

    def fail_finish(agent_id, event, *, source):
        if event is MemberEvent.TASK_FINISHED:
            raise RuntimeError("finish failed")
        return original(agent_id, event, source=source)

    monkeypatch.setattr(team.member_registry, "transition", fail_finish)
    handlers["assign_team_task"](ToolContext(master), task_id=task.id, agent_id=member.agent_id)
    assert load_task(task.id, store=team.task_store).status == "completed"
    assert team.member_registry.get(member.agent_id).state is MemberState.BUSY
    assert "StopPendingTaskError" in handlers["shutdown_teammate"](ToolContext(master), agent_id=member.agent_id)

    monkeypatch.setattr(team.member_registry, "transition", original)
    result = json.loads(handlers["resume_team_task"](ToolContext(master), task_id=task.id, agent_id=member.agent_id))
    assert result["status"] == "completed"
    assert json.loads(handlers["shutdown_teammate"](ToolContext(master), agent_id=member.agent_id))["status"] == "stopped"


def test_teardown_continues_after_injected_member_stop_failure(tmp_path, monkeypatch):
    team, master, handlers = make_team(tmp_path)
    first = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="first")
    second = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="second")
    original = team.lifecycle_manager.shutdown

    def fail_first(agent_id):
        if agent_id == first.agent_id:
            raise RuntimeError("stop failed")
        return original(agent_id)

    monkeypatch.setattr(team.lifecycle_manager, "shutdown", fail_first)
    partial = json.loads(handlers["teardown_team"](ToolContext(master)))
    assert partial["failures"][first.agent_id]["message"] == "stop failed"
    assert second.agent_id in partial["stopped"]
    assert team.member_registry.get(first.agent_id).state is MemberState.IDLE
    assert team.member_registry.get(second.agent_id).state is MemberState.STOPPED

    monkeypatch.setattr(team.lifecycle_manager, "shutdown", original)
    assert json.loads(handlers["teardown_team"](ToolContext(master)))["released"] is True


def test_teardown_reports_release_failure_and_keeps_terminal_records(tmp_path, monkeypatch):
    team, master, handlers = make_team(tmp_path)
    member = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    original = team.member_registry.release_all

    def fail_release(*, reason):
        raise RuntimeError("registry cleanup failed")

    monkeypatch.setattr(team.member_registry, "release_all", fail_release)
    partial = json.loads(handlers["teardown_team"](ToolContext(master)))
    assert partial["status"] == "partial"
    assert partial["failures"]["release"]["message"] == "registry cleanup failed"
    assert team.member_registry.get(member.agent_id).state is MemberState.STOPPED

    monkeypatch.setattr(team.member_registry, "release_all", original)
    assert json.loads(handlers["teardown_team"](ToolContext(master)))["released"] is True


def test_mailbox_cleanup_failure_keeps_terminal_records_and_messages(tmp_path, monkeypatch):
    team, master, handlers = make_team(tmp_path)
    sender = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="sender")
    target = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="target")
    team.lifecycle_manager.get_agent(sender.agent_id).mailbox_handle.send(target.agent_id, "accepted")
    original = team.message_bus.release

    def fail_release():
        original()
        raise RuntimeError("mailbox cleanup failed")

    monkeypatch.setattr(team.message_bus, "release", fail_release)
    partial = json.loads(handlers["teardown_team"](ToolContext(master)))
    assert partial["status"] == "partial"
    assert partial["failures"]["release"]["message"] == "mailbox cleanup failed"
    assert [item.state for item in team.member_registry.list()] == [MemberState.STOPPED, MemberState.STOPPED]
    assert len(team.message_bus._mailboxes[target.agent_id]) == 1

    monkeypatch.setattr(team.message_bus, "release", original)
    assert json.loads(handlers["teardown_team"](ToolContext(master)))["released"] is True


def test_message_send_waits_for_terminal_transition(tmp_path, monkeypatch):
    team, master, handlers = make_team(tmp_path)
    sender = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="sender")
    target = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="target")
    handle = team.lifecycle_manager.get_agent(sender.agent_id).mailbox_handle
    transition_entered = Event()
    release_transition = Event()
    original = team.member_registry.transition

    def pause_transition(agent_id, event, *, source):
        if agent_id == target.agent_id and event is MemberEvent.SHUTDOWN:
            transition_entered.set()
            assert release_transition.wait(5)
        return original(agent_id, event, source=source)

    monkeypatch.setattr(team.member_registry, "transition", pause_transition)
    with ThreadPoolExecutor(max_workers=2) as executor:
        stop = executor.submit(handlers["shutdown_teammate"], ToolContext(master), agent_id=target.agent_id)
        assert transition_entered.wait(5)
        send = executor.submit(handle.send, target.agent_id, "late")
        release_transition.set()
        assert json.loads(stop.result(timeout=5))["status"] == "stopped"
        with pytest.raises(MessageUnavailableError):
            send.result(timeout=5)
    assert team.message_bus._mailboxes == {}


def test_message_receive_waits_for_fatal_transition(tmp_path, monkeypatch):
    team, master, handlers = make_team(tmp_path)
    sender = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="sender")
    target = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="target")
    team.lifecycle_manager.get_agent(sender.agent_id).mailbox_handle.send(target.agent_id, "accepted")
    handle = team.lifecycle_manager.get_agent(target.agent_id).mailbox_handle
    transition_entered = Event()
    release_transition = Event()
    original = team.member_registry.transition

    def pause_transition(agent_id, event, *, source):
        if agent_id == target.agent_id and event is MemberEvent.FATAL_RUNTIME_ERROR:
            transition_entered.set()
            assert release_transition.wait(5)
        return original(agent_id, event, source=source)

    monkeypatch.setattr(team.member_registry, "transition", pause_transition)
    with ThreadPoolExecutor(max_workers=2) as executor:
        fatal = executor.submit(handlers["report_team_fatal"], ToolContext(master), agent_id=target.agent_id, error="fatal")
        assert transition_entered.wait(5)
        receive = executor.submit(handle.receive)
        release_transition.set()
        assert json.loads(fatal.result(timeout=5))["member_state"] == "failed"
        with pytest.raises(MessageUnavailableError):
            receive.result(timeout=5)
    assert len(team.message_bus._mailboxes[target.agent_id]) == 1


def test_lifecycle_tools_reject_foreign_session_and_released_members(tmp_path):
    team, master, handlers = make_team(tmp_path)
    member = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    foreign = SimpleNamespace(session_id="other")
    for name, args in (
        ("shutdown_teammate", {"agent_id": member.agent_id}),
        ("teardown_team", {}),
        ("report_team_fatal", {"agent_id": member.agent_id, "error": "fatal"}),
        ("recover_failed_team_task", {"task_id": "TASK-00000000"}),
    ):
        assert "TeamError" in handlers[name](ToolContext(foreign), **args)
    assert team.member_registry.get(member.agent_id).state is MemberState.IDLE
    assert json.loads(handlers["teardown_team"](ToolContext(master)))["released"] is True
    assert "MessageUnavailableError" in handlers["shutdown_teammate"](ToolContext(master), agent_id=member.agent_id)
    assert "MessageUnavailableError" in handlers["create_team_task"](ToolContext(master), subject="late")
    assert "MessageUnavailableError" in handlers["recover_failed_team_task"](
        ToolContext(master), task_id="TASK-00000000"
    )
