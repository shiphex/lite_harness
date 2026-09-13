"""Team-level use case 的 orchestration dependency boundary。"""

from typing import TYPE_CHECKING

from tools.task_system import TaskStore

from .contracts import MemberRecord
from .lifecycle import LifecycleManager
from .messaging import MessageBus
from .registry import MemberRegistry

if TYPE_CHECKING:
    from core.runtime import AgentRuntime


class TeamCoordinator:
    """持有 shared services；use-case 行为在后续 vertical slices 实现。"""

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
