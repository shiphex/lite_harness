import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Barrier, Event
from types import SimpleNamespace

import pytest

from core.runtime import RuntimeFactory
from team.agent import TeamAgent
from team.contracts import MemberEvent, MemberState
from team.runtime import TeamRuntime
from tools.task_system import (
    TaskClaimConflict,
    TaskStore,
    claim_task_strict,
    complete_task_strict,
    create_task,
    load_task,
    update_task,
)
from tools.team import bind_team_handlers
from tools.tool_class import ToolContext


def make_team(tmp_path, loop, session_id="session-1"):
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


def test_master_can_create_assign_and_complete_team_task(tmp_path):
    seen = []

    def loop(runtime):
        task_id = json.loads(runtime.state.messages[-1]["content"])["task_id"]
        seen.append(task_id)
        result = runtime.tools.execute(
            ToolContext(runtime), "complete_team_task", {"task_id": task_id}
        )
        assert json.loads(result)["status"] == "completed"
        return runtime.state, {"reason": "completed"}

    team, master, handlers = make_team(tmp_path, loop)
    member = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    created = json.loads(
        handlers["create_team_task"](ToolContext(master), subject="first", description="do it")
    )
    task_id = created["task"]["id"]
    assert task_id in handlers["list_team_tasks"](ToolContext(master))
    assert json.loads(handlers["get_team_task"](ToolContext(master), task_id=task_id))["task"]["id"] == task_id

    result = json.loads(
        handlers["assign_team_task"](
            ToolContext(master), task_id=task_id, agent_id=member.agent_id
        )
    )

    assert result["status"] == "completed"
    assert seen == [task_id]
    assert load_task(task_id, store=team.task_store).owner == member.agent_id
    assert load_task(task_id, store=team.task_store).status == "completed"
    assert team.member_registry.get(member.agent_id).state is MemberState.IDLE
    assert team.lifecycle_manager.get_agent(member.agent_id).mailbox_handle.receive() is None


def test_incomplete_turn_can_only_resume_for_same_owner(tmp_path):
    calls = []

    def loop(runtime):
        calls.append(runtime.agent_id)
        return runtime.state, {"reason": "max_turns"}

    team, master, handlers = make_team(tmp_path, loop)
    first = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="first")
    second = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="second")
    task = create_task("work", "", store=team.task_store)
    assign = handlers["assign_team_task"]
    resume = handlers["resume_team_task"]

    result = json.loads(assign(ToolContext(master), task_id=task.id, agent_id=first.agent_id))
    assert result["status"] == "in_progress"
    assert team.member_registry.get(first.agent_id).state is MemberState.BUSY
    assert "Team error" in resume(ToolContext(master), task_id=task.id, agent_id=second.agent_id)
    assert json.loads(resume(ToolContext(master), task_id=task.id, agent_id=first.agent_id))["status"] == "in_progress"
    assert calls == [first.agent_id, first.agent_id]


def test_team_task_tools_are_bound_and_cannot_forge_runtime(tmp_path, monkeypatch):
    team, master, _ = make_team(tmp_path, lambda runtime: (runtime.state, {"reason": "completed"}))
    member = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    runtime = team.lifecycle_manager.get_agent(member.agent_id).runtime
    names = {tool["name"] for tool in runtime.policy.tools_list}
    assert runtime.policy.allow_background_tools is False
    bash_schema = next(tool["input_schema"] for tool in runtime.policy.tools_list if tool["name"] == "bash")
    assert "run_in_background" not in bash_schema["properties"]
    assert {"bash", "write_file", "edit_file", "get_team_task", "create_team_task", "update_team_task", "complete_team_task"} <= names
    assert "claim_task" not in names
    assert "TASK05_READY" in runtime.tools.execute(
        ToolContext(runtime), "bash", {"command": "echo TASK05_READY"}
    )
    monkeypatch.setattr("tools.file_option.WORKDIR", tmp_path)
    assert "成功" in runtime.tools.execute(
        ToolContext(runtime), "write_file", {"path": "output.txt", "content": "before"}
    )
    assert "成功" in runtime.tools.execute(
        ToolContext(runtime), "edit_file",
        {"path": "output.txt", "old_text": "before", "new_text": "after"},
    )
    assert (tmp_path / "output.txt").read_text(encoding="utf-8") == "after"
    task = create_task("work", "", store=team.task_store)
    forged = SimpleNamespace(agent_id=member.agent_id)
    result = runtime.policy.tool_handler["get_team_task"](ToolContext(forged), task_id=task.id)
    assert "Team error" in result


def test_strict_claim_reports_exactly_one_winner(tmp_path):
    team, _, _ = make_team(tmp_path, lambda runtime: (runtime.state, {"reason": "completed"}))
    task = create_task("work", "", store=team.task_store)
    gate = Barrier(2)

    def claim(owner):
        gate.wait()
        try:
            return claim_task_strict(task.id, owner, store=team.task_store).owner
        except TaskClaimConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(claim, ["one", "two"]))
    assert results.count("conflict") == 1
    assert load_task(task.id, store=team.task_store).owner in {"one", "two"}


def test_execution_error_keeps_assignment_and_resume_can_complete(tmp_path):
    calls = []

    def loop(runtime):
        calls.append(runtime.agent_id)
        if len(calls) == 1:
            raise RuntimeError("model failed")
        task_id = json.loads(runtime.state.messages[-1]["content"])["task_id"]
        runtime.tools.execute(ToolContext(runtime), "complete_team_task", {"task_id": task_id})
        return runtime.state, {"reason": "completed"}

    team, master, handlers = make_team(tmp_path, loop)
    member = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    task = create_task("work", "", store=team.task_store)
    first = json.loads(handlers["assign_team_task"](ToolContext(master), task_id=task.id, agent_id=member.agent_id))
    assert first["status"] == "execution_error"
    assert first["task_status"] == "in_progress"
    assert first["member_state"] == "busy"
    second = json.loads(handlers["resume_team_task"](ToolContext(master), task_id=task.id, agent_id=member.agent_id))
    assert second["status"] == "completed"
    assert calls == [member.agent_id, member.agent_id]


def test_resume_repairs_claimed_task_after_member_transition_failure(tmp_path, monkeypatch):
    calls = []

    def loop(runtime):
        calls.append(runtime.agent_id)
        return runtime.state, {"reason": "max_turns"}

    team, master, handlers = make_team(tmp_path, loop)
    member = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    task = create_task("work", "", store=team.task_store)
    transition = team.member_registry.transition
    failed = False

    def fail_once(agent_id, event, *, source):
        nonlocal failed
        if event is MemberEvent.TASK_CLAIMED and not failed:
            failed = True
            raise RuntimeError("registry unavailable")
        return transition(agent_id, event, source=source)

    monkeypatch.setattr(team.member_registry, "transition", fail_once)
    failed_result = json.loads(
        handlers["assign_team_task"](
            ToolContext(master), task_id=task.id, agent_id=member.agent_id
        )
    )
    assert failed_result["status"] == "inconsistent"
    assert "registry unavailable" in failed_result["error"]
    assert load_task(task.id, store=team.task_store).status == "in_progress"
    assert team.member_registry.get(member.agent_id).state is MemberState.IDLE
    other_task = create_task("other", "", store=team.task_store)
    rejected = handlers["assign_team_task"](
        ToolContext(master), task_id=other_task.id, agent_id=member.agent_id
    )
    assert "Team error" in rejected
    assert load_task(other_task.id, store=team.task_store).status == "pending"
    result = team.coordinator.resume_task(task.id, member.agent_id)
    assert result["status"] == "in_progress"
    assert calls == [member.agent_id]


def test_resume_repairs_member_after_task_completed(tmp_path, monkeypatch):
    calls = []

    def loop(runtime):
        calls.append(runtime.agent_id)
        task_id = json.loads(runtime.state.messages[-1]["content"])["task_id"]
        result = runtime.tools.execute(ToolContext(runtime), "complete_team_task", {"task_id": task_id})
        assert "Team error" in result
        return runtime.state, {"reason": "completed"}

    team, master, handlers = make_team(tmp_path, loop)
    member = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    task = create_task("work", "", store=team.task_store)
    transition = team.member_registry.transition
    failed = False

    def fail_once(agent_id, event, *, source):
        nonlocal failed
        if event is MemberEvent.TASK_FINISHED and not failed:
            failed = True
            raise RuntimeError("registry unavailable")
        return transition(agent_id, event, source=source)

    monkeypatch.setattr(team.member_registry, "transition", fail_once)
    first = json.loads(handlers["assign_team_task"](ToolContext(master), task_id=task.id, agent_id=member.agent_id))
    assert first["status"] == "inconsistent"
    assert first["task_status"] == "completed"
    assert first["member_state"] == "busy"
    repaired = json.loads(handlers["resume_team_task"](ToolContext(master), task_id=task.id, agent_id=member.agent_id))
    assert repaired["status"] == "completed"
    assert calls == [member.agent_id]


def test_member_cannot_be_reassigned_during_active_turn(tmp_path):
    entered = Event()
    release = Event()

    def loop(runtime):
        entered.set()
        assert release.wait(5)
        return runtime.state, {"reason": "max_turns"}

    team, master, handlers = make_team(tmp_path, loop)
    member = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    first = create_task("first", "", store=team.task_store)
    second = create_task("second", "", store=team.task_store)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(team.coordinator.assign_task, first.id, member.agent_id)
        assert entered.wait(5)
        try:
            result = handlers["assign_team_task"](ToolContext(master), task_id=second.id, agent_id=member.agent_id)
            assert "Team error" in result
            assert load_task(second.id, store=team.task_store).status == "pending"
        finally:
            release.set()
        assert future.result()["status"] == "in_progress"


def test_team_task_creation_and_dependency_tools_use_local_store(tmp_path, monkeypatch):
    global_store = TaskStore(tmp_path / "global")
    monkeypatch.setattr("tools.task_system.TASKS", global_store)
    team, master, _ = make_team(tmp_path, lambda runtime: (runtime.state, {"reason": "completed"}))
    member = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    runtime = team.lifecycle_manager.get_agent(member.agent_id).runtime
    context = ToolContext(runtime)
    first = json.loads(runtime.tools.execute(context, "create_team_task", {"subject": "first"}))["task"]
    second = json.loads(runtime.tools.execute(context, "create_team_task", {"subject": "second"}))["task"]
    updated = json.loads(runtime.tools.execute(
        context,
        "update_team_task",
        {"task_id": second["id"], "addBlockedBy": [first["id"]]},
    ))
    assert updated["task"]["blockedBy"] == [first["id"]]
    assert json.loads(runtime.tools.execute(context, "get_team_task", {"task_id": second["id"]}))["task"]["id"] == second["id"]
    assert team.task_store.exists(first["id"])
    assert not global_store.exists(first["id"])


def test_team_task_creation_rejects_non_text_subject_without_aborting_loop(tmp_path):
    team, master, handlers = make_team(tmp_path, lambda runtime: (runtime.state, {"reason": "completed"}))
    member = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    runtime = team.lifecycle_manager.get_agent(member.agent_id).runtime
    assert "TaskError" in handlers["create_team_task"](ToolContext(master), subject=None)
    assert "TaskError" in handlers["create_team_task"](
        ToolContext(master), subject="valid", description=None
    )
    assert "TaskError" in runtime.tools.execute(
        ToolContext(runtime), "create_team_task", {"subject": 7}
    )
    assert team.task_store.list() == []


def test_assignment_rejects_unmet_dependency_and_other_team_member(tmp_path):
    team, master, handlers = make_team(tmp_path, lambda runtime: (runtime.state, {"reason": "completed"}))
    other, other_master, other_handlers = make_team(tmp_path, lambda runtime: (runtime.state, {"reason": "completed"}), "session-2")
    member = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    outsider = other.coordinator.spawn_teammate(parent_runtime=other_master, agent_name="outsider")
    blocker = create_task("blocker", "", store=team.task_store)
    blocked = create_task("blocked", "", store=team.task_store)
    team.task_store.update_dependencies(blocked.id, [blocker.id])
    assign = handlers["assign_team_task"]
    assert "Team error" in assign(ToolContext(master), task_id=blocked.id, agent_id=member.agent_id)
    assert "Team error" in assign(ToolContext(master), task_id=blocker.id, agent_id=outsider.agent_id)
    assert "Team error" in other_handlers["get_team_task"](ToolContext(other_master), task_id=blocker.id)
    assert load_task(blocked.id, store=team.task_store).status == "pending"


def test_duplicate_completion_is_rejected_without_changing_member(tmp_path):
    observed = []

    def loop(runtime):
        task_id = json.loads(runtime.state.messages[-1]["content"])["task_id"]
        first = runtime.tools.execute(ToolContext(runtime), "complete_team_task", {"task_id": task_id})
        second = runtime.tools.execute(ToolContext(runtime), "complete_team_task", {"task_id": task_id})
        observed.extend((first, second))
        return runtime.state, {"reason": "completed"}

    team, master, handlers = make_team(tmp_path, loop)
    member = team.coordinator.spawn_teammate(parent_runtime=master, agent_name="worker")
    task = create_task("work", "", store=team.task_store)
    result = json.loads(handlers["assign_team_task"](ToolContext(master), task_id=task.id, agent_id=member.agent_id))
    assert result["status"] == "completed"
    assert json.loads(observed[0])["status"] == "completed"
    assert "TaskCompletionConflict" in observed[1]
    assert team.member_registry.get(member.agent_id).state is MemberState.IDLE


def test_dependency_update_cannot_overwrite_concurrent_claim(tmp_path, monkeypatch):
    team, _, _ = make_team(tmp_path, lambda runtime: (runtime.state, {"reason": "completed"}))
    dependency = create_task("dependency", "", store=team.task_store)
    claim_task_strict(dependency.id, "owner", store=team.task_store)
    complete_task_strict(dependency.id, "owner", store=team.task_store)
    target = create_task("target", "", store=team.task_store)
    entered = Event()
    release = Event()
    original_save = team.task_store.save

    def paused_save(task):
        if task.id == target.id and task.status == "pending":
            entered.set()
            assert release.wait(5)
        return original_save(task)

    monkeypatch.setattr(team.task_store, "save", paused_save)
    with ThreadPoolExecutor(max_workers=2) as executor:
        update_future = executor.submit(
            update_task, target.id, [dependency.id], store=team.task_store
        )
        assert entered.wait(5)
        claim_future = executor.submit(
            claim_task_strict, target.id, "worker", store=team.task_store
        )
        try:
            claim_future.result(timeout=0.2)
        except TimeoutError:
            pass
        finally:
            release.set()
        claim_future.result(timeout=5)
        update_future.result(timeout=5)
    saved = load_task(target.id, store=team.task_store)
    assert saved.status == "in_progress"
    assert saved.blockedBy == [dependency.id]


def test_team_read_waits_for_same_store_claim_write(tmp_path, monkeypatch):
    team, _, _ = make_team(tmp_path, lambda runtime: (runtime.state, {"reason": "completed"}))
    task = create_task("work", "", store=team.task_store)
    entered = Event()
    release = Event()
    original_save = team.task_store.save

    def paused_save(updated):
        team.task_store._path(updated.id).write_text("{", encoding="utf-8")
        entered.set()
        assert release.wait(5)
        original_save(updated)

    monkeypatch.setattr(team.task_store, "save", paused_save)
    with ThreadPoolExecutor(max_workers=2) as executor:
        claim_future = executor.submit(
            claim_task_strict, task.id, "worker", store=team.task_store
        )
        assert entered.wait(5)
        read_future = executor.submit(load_task, task.id, store=team.task_store)
        try:
            read_future.result(timeout=0.2)
        except TimeoutError:
            pass
        finally:
            release.set()
        claim_future.result(timeout=5)
        assert read_future.result(timeout=5).status == "in_progress"
