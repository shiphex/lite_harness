"""一支 Agent Team 的 composition root。"""

from pathlib import Path

from core.runtime import RuntimeFactory
from tools.task_system import TaskStore

from .coordinator import TeamCoordinator
from .agent import TeamAgent
from .lifecycle import LifecycleManager
from .messaging import MessageBus
from .registry import MemberRegistry


class TeamRuntime:
    """组装并持有一支 team 的唯一 shared service instances。"""

    def __init__(
        self,
        task_directory: Path,
        *,
        session_id: str | None = None,
        runtime_factory: type[RuntimeFactory] = RuntimeFactory,
        agent_factory=TeamAgent,
    ):
        self.session_id = session_id
        self.member_registry = MemberRegistry()
        self.message_bus = MessageBus()
        self.task_store = TaskStore(Path(task_directory))
        self.lifecycle_manager = LifecycleManager(
            member_registry=self.member_registry,
            runtime_factory=runtime_factory,
            session_id=session_id,
            agent_factory=agent_factory,
        )
        self.coordinator = TeamCoordinator(
            member_registry=self.member_registry,
            message_bus=self.message_bus,
            task_store=self.task_store,
            lifecycle_manager=self.lifecycle_manager,
        )
