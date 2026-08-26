from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

from tools.task_system import (
    TaskStore,
    bind_task_handlers,
    claim_task,
    complete_task,
)
from tools.tool_class import ToolContext


def test_task_store_instances_are_isolated(tmp_path):
    """不同 team 的 TaskStore 不应共享任务。"""

    first = TaskStore(tmp_path / "first")
    second = TaskStore(tmp_path / "second")

    task = first.create("first task", "")

    assert [item.id for item in first.list()] == [task.id]
    assert second.list() == []


def test_concurrent_claim_allows_only_one_owner(tmp_path):
    """并发 claim 必须作为一个完整事务执行。"""

    store = TaskStore(tmp_path / "tasks")
    task = store.create("shared task", "")
    barrier = Barrier(8)

    def claim(index):
        barrier.wait()
        return claim_task(task.id, owner=f"worker-{index}", store=store)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(claim, range(8)))

    assert sum(result.startswith("Claimed") for result in results) == 1
    claimed = store.load(task.id)
    assert claimed.status == "in_progress"
    assert claimed.owner is not None


def test_complete_task_unlocks_dependency_in_bound_store(tmp_path):
    """完成任务时应只读取和更新绑定的 team TaskStore。"""

    store = TaskStore(tmp_path / "tasks")
    dependency = store.create("dependency", "")
    blocked = store.create("blocked", "")
    store.update_dependencies(blocked.id, [dependency.id])

    assert "未完成依赖" in claim_task(blocked.id, owner="bob", store=store)
    claim_task(dependency.id, owner="alice", store=store)
    result = complete_task(dependency.id, owner="alice", store=store)

    assert "Unlocked: blocked" in result
    assert claim_task(blocked.id, owner="bob", store=store).startswith("Claimed")


def test_bind_task_handlers_uses_injected_store(tmp_path):
    """绑定后的 task handlers 应只读写指定 TaskStore。"""

    store = TaskStore(tmp_path / "tasks")
    task = store.create("assigned", "")
    claim_task(task.id, owner="alice", store=store)
    handlers = bind_task_handlers(store)
    context = ToolContext(SimpleNamespace(agent_name="alice"))

    assert set(handlers) == {
        "create_task",
        "update_task",
        "list_tasks",
        "get_task",
        "claim_task",
        "complete_task",
    }
    assert task.id in handlers["get_task"](context, task_id=task.id)
    assert handlers["complete_task"](
        context,
        task_id=task.id,
    ).startswith("Completed")
