"""Agent Team 的共享运行时与核心契约。"""

from .agent import TeamAgent
from .contracts import (
    DuplicateMemberError,
    InvalidMessageError,
    InvalidMemberTransitionError,
    MailboxFullError,
    MemberEvent,
    MemberNotFoundError,
    MemberRecord,
    MemberState,
    MessageTargetNotFoundError,
    MessageUnavailableError,
    SpawnError,
    TeamError,
    TransitionSource,
    UnauthorizedMemberOperationError,
    UnregisterReason,
)
from .coordinator import TeamCoordinator
from .lifecycle import LifecycleManager
from .messaging import MailboxHandle, MessageBus, TeamMessage
from .registry import MemberRegistry
from .runtime import TeamRuntime

__all__ = [
    "DuplicateMemberError",
    "InvalidMessageError",
    "InvalidMemberTransitionError",
    "LifecycleManager",
    "MemberEvent",
    "MemberNotFoundError",
    "MemberRecord",
    "MemberRegistry",
    "MemberState",
    "MailboxFullError",
    "MailboxHandle",
    "MessageBus",
    "MessageTargetNotFoundError",
    "MessageUnavailableError",
    "TeamMessage",
    "TeamCoordinator",
    "TeamAgent",
    "TeamError",
    "TeamRuntime",
    "TransitionSource",
    "SpawnError",
    "UnauthorizedMemberOperationError",
    "UnregisterReason",
]
