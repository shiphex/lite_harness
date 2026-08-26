"""Agent Teams 协作平面。"""

from .contract import MemberStatus, TeamMember, TeamMessage


def __getattr__(name: str):
    """延迟导出 Coordinator 和 Runtime factory，避免包初始化循环依赖。"""

    if name in {"TeamCoordinator", "TeamError"}:
        from .coordinator import TeamCoordinator, TeamError

        return {
            "TeamCoordinator": TeamCoordinator,
            "TeamError": TeamError,
        }[name]
    if name == "create_teammate_runtime":
        from .factory import create_teammate_runtime

        return create_teammate_runtime
    raise AttributeError(name)


__all__ = [
    "MemberStatus",
    "TeamMember",
    "TeamMessage",
    "TeamCoordinator",
    "TeamError",
    "create_teammate_runtime",
]
