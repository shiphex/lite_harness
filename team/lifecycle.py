"""TeamAgent lifecycle dependency boundary。"""

from core.runtime import RuntimeFactory

from .registry import MemberRegistry


class LifecycleManager:
    """持有 lifecycle 所需依赖；worker 行为在后续 phase 实现。"""

    def __init__(
        self,
        *,
        member_registry: MemberRegistry,
        runtime_factory: type[RuntimeFactory] = RuntimeFactory,
    ):
        self.member_registry = member_registry
        self.runtime_factory = runtime_factory
