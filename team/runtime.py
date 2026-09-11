"""一支 Agent Team 的 composition root。"""

from pathlib import Path

from core.runtime import RuntimeFactory
from tools.task_system import TaskStore

from .coordinator import TeamCoordinator
from .lifecycle import LifecycleManager
from .messaging import MessageBus
from .registry import MemberRegistry


class TeamRuntime:
    """组装并持有一支 team 的唯一 shared service instances。"""

    def __init__(
        self,
        task_directory: Path,
        *,
        runtime_factory: type[RuntimeFactory] = RuntimeFactory,
    ):
        self.member_registry = MemberRegistry()
        self.message_bus = MessageBus()
        self.task_store = TaskStore(Path(task_directory))
        self.lifecycle_manager = LifecycleManager(
            member_registry=self.member_registry,
            runtime_factory=runtime_factory,
        )
        self.coordinator = TeamCoordinator(
            member_registry=self.member_registry,
            message_bus=self.message_bus,
            task_store=self.task_store,
            lifecycle_manager=self.lifecycle_manager,
        )
