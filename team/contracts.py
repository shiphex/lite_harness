"""Agent Team Phase 1 使用的数据与错误契约。"""

from dataclasses import dataclass
from enum import StrEnum


class MemberState(StrEnum):
    """Team member 的可观察生命周期状态。"""

    STARTING = "starting"
    IDLE = "idle"
    BUSY = "busy"
    WAITING = "waiting"
    STOPPED = "stopped"
    FAILED = "failed"


class MemberEvent(StrEnum):
    """可以提交给 MemberRegistry 的状态转换事件。"""

    SPAWN_SUCCESS = "spawn_success"
    TASK_CLAIMED = "task_claimed"
    DEPENDENCY_WAIT = "dependency_wait"
    DEPENDENCY_RESOLVED = "dependency_resolved"
    TASK_FINISHED = "task_finished"
    SHUTDOWN = "shutdown"
    FATAL_RUNTIME_ERROR = "fatal_runtime_error"


class TransitionSource(StrEnum):
    """被允许报告 MemberState 变化的模块身份。"""

    LIFECYCLE_MANAGER = "lifecycle_manager"
    TEAM_COORDINATOR = "team_coordinator"
    TEAM_AGENT = "team_agent"
    TASK_STORE = "task_store"
    RUNTIME_SUPERVISOR = "runtime_supervisor"


class UnregisterReason(StrEnum):
    """允许从 registry 删除 member record 的两个边界。"""

    SPAWN_ROLLBACK = "spawn_rollback"
    TEAM_RELEASE = "team_release"


@dataclass(frozen=True, slots=True)
class MemberRecord:
    """MemberRegistry 对外暴露的不可变 member snapshot。"""

    agent_id: str
    agent_name: str
    state: MemberState


class TeamError(ValueError):
    """可预期的 Agent Team domain error。"""


class DuplicateMemberError(TeamError):
    """注册重复 agent_id 时抛出。"""


class MemberNotFoundError(TeamError):
    """查询不存在的 member 时抛出。"""


class InvalidMemberTransitionError(TeamError):
    """MemberState 状态机拒绝 transition 时抛出。"""


class UnauthorizedMemberOperationError(TeamError):
    """调用来源或 unregister 用途不符合契约时抛出。"""


class SpawnError(TeamError):
    """TeamAgent spawn transaction 失败时抛出。"""
