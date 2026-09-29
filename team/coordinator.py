"""Team-level use case 的 orchestration dependency boundary。"""

from typing import TYPE_CHECKING
import json
from threading import Lock, RLock

from tools.task_system import (
    TaskStore,
    claim_task_strict,
    create_task,
    list_tasks,
    load_task,
)

from .contracts import (
    MemberEvent,
    MemberRecord,
    MemberState,
    TeamError,
    TransitionSource,
)
from .lifecycle import LifecycleManager
from .messaging import MessageBus
from .registry import MemberRegistry

if TYPE_CHECKING:
    from core.runtime import AgentRuntime


class TeamCoordinator:
    """编排 TeamRuntime 的 spawn 与显式任务执行 use case。"""

    def __init__(
        self,
        *,
        member_registry: MemberRegistry,
        message_bus: MessageBus,
        task_store: TaskStore,
        lifecycle_manager: LifecycleManager,
    ):
        self.member_registry = member_registry
        self.message_bus = message_bus
        self.task_store = task_store
        self.lifecycle_manager = lifecycle_manager
        self._execution_locks: dict[str, Lock] = {}
        self._locks_guard = RLock()

    def spawn_teammate(
        self,
        *,
        parent_runtime: "AgentRuntime",
        agent_name: str,
    ) -> MemberRecord:
        """将 spawn use case 委托给唯一 lifecycle 入口。"""

        return self.lifecycle_manager.spawn(
            parent_runtime=parent_runtime,
            agent_name=agent_name,
        )

    def create_task(self, subject: str, description: str = ""):
        return create_task(subject, description, store=self.task_store)

    def list_tasks(self):
        return list_tasks(store=self.task_store)

    def get_task(self, task_id: str):
        return load_task(task_id, store=self.task_store)

    def _execution_lock(self, agent_id: str) -> Lock:
        with self._locks_guard:
            return self._execution_locks.setdefault(agent_id, Lock())

    def assign_task(self, task_id: str, agent_id: str) -> dict:
        return self._execute_task(task_id, agent_id, resume=False)

    def resume_task(self, task_id: str, agent_id: str) -> dict:
        return self._execute_task(task_id, agent_id, resume=True)

    def _execute_task(self, task_id: str, agent_id: str, *, resume: bool) -> dict:
        agent = self.lifecycle_manager.get_agent(agent_id)
        lock = self._execution_lock(agent_id)
        if not lock.acquire(blocking=False):
            raise TeamError(f"TeamAgent {agent_id!r} 正在执行另一轮任务")
        try:
            member = self.member_registry.get(agent_id)
            task = load_task(task_id, store=self.task_store)
            owned_active = {
                candidate.id
                for candidate in list_tasks(store=self.task_store)
                if candidate.owner == agent_id and candidate.status == "in_progress"
            }
            if resume:
                if task.owner != agent_id or task.status not in {"in_progress", "completed"}:
                    raise TeamError("只能由原 owner 续跑已领取任务")
                if owned_active - {task_id}:
                    raise TeamError("目标成员还有其他未完成任务，不能续跑")
                if task.status == "completed":
                    if member.state is not MemberState.BUSY:
                        raise TeamError("已完成任务没有待恢复的成员状态")
                    try:
                        agent.report_task_finished(self.member_registry)
                    except Exception as exc:
                        return self._result(
                            "transition_error", task_id, agent_id,
                            error=f"{type(exc).__name__}: {exc}",
                        )
                    return self._result("completed", task_id, agent_id)
                if member.state is MemberState.IDLE:
                    try:
                        self.member_registry.transition(
                            agent_id,
                            MemberEvent.TASK_CLAIMED,
                            source=TransitionSource.TEAM_COORDINATOR,
                        )
                    except Exception as exc:
                        return self._result(
                            "transition_error", task_id, agent_id,
                            error=f"{type(exc).__name__}: {exc}",
                        )
                elif member.state is not MemberState.BUSY:
                    raise TeamError("目标成员当前状态不能续跑任务")
            else:
                if member.state is not MemberState.IDLE:
                    raise TeamError("目标成员不是 IDLE")
                if owned_active:
                    raise TeamError("目标成员仍有已领取任务，须先显式续跑")
                claim_task_strict(task_id, agent_id, store=self.task_store)
                try:
                    self.member_registry.transition(
                        agent_id,
                        MemberEvent.TASK_CLAIMED,
                        source=TransitionSource.TEAM_COORDINATOR,
                    )
                except Exception as exc:
                    return self._result(
                        "transition_error", task_id, agent_id,
                        error=f"{type(exc).__name__}: {exc}",
                    )

            agent.active_task_id = task_id
            prompt = json.dumps(
                {
                    "task_id": task.id,
                    "subject": task.subject,
                    "description": task.description,
                    "instruction": "执行此任务；完成后调用 complete_team_task。",
                },
                ensure_ascii=False,
            )
            try:
                _, run_status = agent.run(prompt)
                return self._result("turn_finished", task_id, agent_id, run_status)
            except Exception as exc:
                return self._result(
                    "execution_error",
                    task_id,
                    agent_id,
                    error=f"{type(exc).__name__}: {exc}",
                )
            finally:
                agent.active_task_id = None
        finally:
            lock.release()

    def _result(
        self,
        outcome: str,
        task_id: str,
        agent_id: str,
        run_status=None,
        *,
        error: str | None = None,
    ) -> dict:
        task = load_task(task_id, store=self.task_store)
        member = self.member_registry.get(agent_id)
        status = (
            "completed" if task.status == "completed" and member.state is MemberState.IDLE
            else "in_progress" if task.status == "in_progress" and member.state is MemberState.BUSY
            else "inconsistent"
        )
        if outcome == "execution_error":
            status = "execution_error"
        return {
            "status": status,
            "task_id": task_id,
            "agent_id": agent_id,
            "task_status": task.status,
            "member_state": member.state,
            "run_reason": run_status.get("reason") if isinstance(run_status, dict) else None,
            "error": error,
        }
