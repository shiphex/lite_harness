"""Agent Teams 协作平面。"""

from .contract import MemberStatus, TeamMember, TeamMessage, TeammateProfile


def __getattr__(name: str):
    """延迟导出 Coordinator 和 Runtime factory，避免包初始化循环依赖。"""

    if name in {"TeamCoordinator", "TeamError", "TeamPermissionError"}:
        from .coordinator import TeamCoordinator, TeamError, TeamPermissionError

        return {
            "TeamCoordinator": TeamCoordinator,
            "TeamError": TeamError,
            "TeamPermissionError": TeamPermissionError,
        }[name]
    if name in {"WorktreeManager", "WorktreeError", "WorktreeHandle"}:
        from .worktree import WorktreeError, WorktreeHandle, WorktreeManager

        return {
            "WorktreeManager": WorktreeManager,
            "WorktreeError": WorktreeError,
            "WorktreeHandle": WorktreeHandle,
        }[name]
    if name == "create_teammate_runtime":
        from .factory import create_teammate_runtime

        return create_teammate_runtime
    raise AttributeError(name)


__all__ = [
    "MemberStatus",
    "TeamMember",
    "TeamMessage",
    "TeammateProfile",
    "TeamCoordinator",
    "TeamError",
    "TeamPermissionError",
    "WorktreeManager",
    "WorktreeError",
    "WorktreeHandle",
    "create_teammate_runtime",
]
