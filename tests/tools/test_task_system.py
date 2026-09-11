import json
from types import SimpleNamespace

from tools import task_system


def test_task_operations_use_the_explicit_store_end_to_end(tmp_path, monkeypatch):
    global_store = task_system.TaskStore(tmp_path / "global")
    team_store = task_system.TaskStore(tmp_path / "team")
    monkeypatch.setattr(task_system, "TASKS", global_store)

    global_task = task_system.create_task("global", "global task")
    dependency = task_system.create_task(
        "dependency",
        "team dependency",
        store=team_store,
    )
    dependent = task_system.create_task(
        "dependent",
        "team dependent",
        store=team_store,
    )
    task_system.update_task(
        dependent.id,
        [dependency.id],
        store=team_store,
    )

    assert task_system.load_task(global_task.id).subject == "global"
    assert [task.id for task in task_system.list_tasks()] == [global_task.id]
    assert {task.id for task in task_system.list_tasks(store=team_store)} == {
        dependency.id,
        dependent.id,
    }
    assert json.loads(task_system.get_task(dependent.id, store=team_store))[
        "blockedBy"
    ] == [dependency.id]
    assert task_system.can_start(dependent.id, store=team_store) is False
    assert "不能被领取" in task_system.claim_task(
        dependent.id,
        owner="teammate",
        store=team_store,
    )

    assert task_system.claim_task(
        dependency.id,
        owner="teammate",
        store=team_store,
    ).startswith("Claimed")
    assert task_system.complete_task(
        dependency.id,
        owner="teammate",
        store=team_store,
    ).startswith("Completed")
    assert task_system.can_start(dependent.id, store=team_store) is True
    assert task_system.claim_task(
        dependent.id,
        owner="teammate",
        store=team_store,
    ).startswith("Claimed")
    assert task_system.complete_task(
        dependent.id,
        owner="teammate",
        store=team_store,
    ).startswith("Completed")
    assert task_system.load_task(
        dependent.id,
        store=team_store,
    ).status == "completed"
    assert task_system.load_task(global_task.id).status == "pending"


def test_existing_tool_handlers_keep_using_dynamic_global_store(
    tmp_path,
    monkeypatch,
):
    global_store = task_system.TaskStore(tmp_path / "global")
    monkeypatch.setattr(task_system, "TASKS", global_store)
    context = SimpleNamespace(
        runtime=SimpleNamespace(agent_name="global-agent"),
    )

    assert task_system.run_create_task(context, "dependency").startswith("Created")
    assert task_system.run_create_task(context, "dependent").startswith("Created")
    tasks_by_subject = {task.subject: task for task in global_store.list()}
    dependency = tasks_by_subject["dependency"]
    dependent = tasks_by_subject["dependent"]
    assert task_system.run_update_task(
        context,
        dependent.id,
        [dependency.id],
    ).startswith("Updated")
    assert dependency.id in task_system.run_get_task(context, dependency.id)
    assert "dependency" in task_system.run_list_tasks(context)
    assert task_system.run_claim_task(context, dependency.id).startswith("Claimed")
    assert task_system.run_complete_task(context, dependency.id).startswith(
        "Completed"
    )
    assert task_system.run_claim_task(context, dependent.id).startswith("Claimed")
    assert task_system.run_complete_task(context, dependent.id).startswith(
        "Completed"
    )
