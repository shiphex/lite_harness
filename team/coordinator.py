"""Team-level use case 的 orchestration dependency boundary。"""

from tools.task_system import TaskStore

from .lifecycle import LifecycleManager
from .messaging import MessageBus
from .registry import MemberRegistry


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
