"""Team-level use case 的 orchestration dependency boundary。"""

from typing import TYPE_CHECKING
from contextlib import ExitStack
import json

from tools.task_system import (
    TaskStore,
    claim_task_strict,
    create_task,
    list_tasks,
    load_task,
    reassign_failed_task_strict,
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

    def shutdown_teammate(self, agent_id: str) -> MemberRecord:
        return self.lifecycle_manager.shutdown(agent_id)

    def teardown_team(self) -> dict:
        return self.lifecycle_manager.teardown()

    def report_fatal(self, agent_id: str, error: str) -> dict:
        return self.lifecycle_manager.report_fatal(agent_id, error)

    def get_member(self, agent_id: str) -> dict:
        return self.lifecycle_manager.member_status(agent_id)

    def create_task(self, subject: str, description: str = ""):
        with self.lifecycle_manager.operation():
            return create_task(subject, description, store=self.task_store)

    def list_tasks(self):
        with self.lifecycle_manager.operation():
            return list_tasks(store=self.task_store)

    def get_task(self, task_id: str):
        with self.lifecycle_manager.operation():
            return load_task(task_id, store=self.task_store)

    def assign_task(self, task_id: str, agent_id: str) -> dict:
        return self._execute_task(task_id, agent_id, resume=False)

    def resume_task(self, task_id: str, agent_id: str) -> dict:
        return self._execute_task(task_id, agent_id, resume=True)

    def recover_failed_task(self, task_id: str, *, parent_runtime: "AgentRuntime") -> dict:
        """显式创建全新成员接手 FAILED owner 的未完成任务。"""
        with ExitStack() as execution_guard:
            with self.lifecycle_manager.operation():
                task = load_task(task_id, store=self.task_store)
                if task.status != "in_progress" or task.owner is None:
                    raise TeamError("只能恢复 FAILED 成员的未完成任务")
                previous_owner = task.owner
                if self.member_registry.get(previous_owner).state is not MemberState.FAILED:
                    raise TeamError("任务原 owner 尚未进入 FAILED 状态")
                member = self.lifecycle_manager.spawn(
                    parent_runtime=parent_runtime,
                    agent_name=f"recovery_{task.id}",
                )
                try:
                    agent = execution_guard.enter_context(
                        self.lifecycle_manager.execution(member.agent_id)
                    )
                    task = reassign_failed_task_strict(
                        task.id, previous_owner, member.agent_id, store=self.task_store
                    )
                except Exception as exc:
                    execution_guard.close()
                    try:
                        self.lifecycle_manager.shutdown(member.agent_id)
                    except Exception as cleanup_exc:
                        raise TeamError(
                            f"任务交接失败: {exc}; 新成员清理失败: {cleanup_exc}"
                        ) from exc
                    raise
                try:
                    self.member_registry.transition(
                        member.agent_id,
                        MemberEvent.TASK_CLAIMED,
                        source=TransitionSource.TEAM_COORDINATOR,
                    )
                except Exception as exc:
                    result = self._result(
                        "transition_error", task.id, member.agent_id,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                    result["previous_owner"] = previous_owner
                    return result
            result = self._run_task_turn(task, member.agent_id, agent)
            result["previous_owner"] = previous_owner
            return result

    def _execute_task(self, task_id: str, agent_id: str, *, resume: bool) -> dict:
        self.lifecycle_manager.ensure_open()
        with self.lifecycle_manager.execution(agent_id) as agent:
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

            return self._run_task_turn(task, agent_id, agent)

    def _run_task_turn(self, task, agent_id: str, agent) -> dict:
        agent.active_task_id = task.id
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
            return self._result("turn_finished", task.id, agent_id, run_status)
        except Exception as exc:
            return self._result(
                "execution_error", task.id, agent_id,
                error=f"{type(exc).__name__}: {exc}",
            )
        finally:
            agent.active_task_id = None

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
