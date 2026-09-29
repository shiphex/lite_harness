"""Team-scoped、同步且有界的内存消息路由。"""

from collections import deque
from dataclasses import dataclass
from threading import RLock

from .contracts import (
    InvalidMessageError,
    MailboxFullError,
    MemberNotFoundError,
    MemberState,
    MessageTargetNotFoundError,
    MessageUnavailableError,
)
from .registry import MemberRegistry


_ACTIVE_STATES = frozenset({MemberState.IDLE, MemberState.BUSY, MemberState.WAITING})
_MAX_CONTENT_LENGTH = 16_384


@dataclass(frozen=True, slots=True)
class TeamMessage:
    sender_id: str
    target_id: str
    content: str


@dataclass(frozen=True, slots=True)
class MailboxHandle:
    """将一个 TeamAgent 的 sender identity 绑定到 MessageBus。"""

    _bus: "MessageBus"
    agent_id: str

    def send(self, target_id: str, content: str) -> None:
        self._bus.send(sender_id=self.agent_id, target_id=target_id, content=content)

    def receive(self) -> TeamMessage | None:
        return self._bus.receive(self.agent_id)


class MessageBus:
    """拥有当前 TeamRuntime 的 mailbox storage 与路由同步。"""

    def __init__(self, registry: MemberRegistry, *, capacity: int = 100):
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValueError("mailbox capacity 必须是正整数")
        self._registry = registry
        self._capacity = capacity
        self._mailboxes: dict[str, deque[TeamMessage]] = {}
        self._lock = RLock()

    def bind(self, agent_id: str) -> MailboxHandle:
        """仅绑定身份；成员可用性在每次收发时检查。"""

        return MailboxHandle(self, agent_id)

    def send(self, *, sender_id: str, target_id: str, content: str) -> None:
        if not isinstance(content, str) or not content.strip():
            raise InvalidMessageError("content 必须是非空文本")
        if len(content) > _MAX_CONTENT_LENGTH:
            raise InvalidMessageError("content 不得超过 16,384 字符")

        with self._lock:
            self._require_active(sender_id, sender=True)
            self._require_active(target_id, sender=False)
            self._enqueue(TeamMessage(sender_id, target_id, content))

    def receive(self, agent_id: str) -> TeamMessage | None:
        with self._lock:
            self._require_active(agent_id, sender=True)
            mailbox = self._mailboxes.get(agent_id)
            return mailbox.popleft() if mailbox else None

    def _enqueue(self, message: TeamMessage) -> None:
        mailbox = self._mailboxes.setdefault(message.target_id, deque())
        if len(mailbox) >= self._capacity:
            raise MailboxFullError(f"member {message.target_id!r} mailbox 已满")
        mailbox.append(message)

    def _require_active(self, agent_id: str, *, sender: bool) -> None:
        if (
            not isinstance(agent_id, str)
            or not agent_id.strip()
            or agent_id != agent_id.strip()
        ):
            if sender:
                raise MessageUnavailableError("sender 不属于当前 TeamRuntime")
            raise MessageTargetNotFoundError("target 不属于当前 TeamRuntime")
        try:
            member = self._registry.get(agent_id)
        except MemberNotFoundError as exc:
            if sender:
                raise MessageUnavailableError(f"sender {agent_id!r} 不存在") from exc
            raise MessageTargetNotFoundError(f"target {agent_id!r} 不存在") from exc
        if member.state not in _ACTIVE_STATES:
            role = "sender" if sender else "target"
            raise MessageUnavailableError(
                f"{role} {agent_id!r} 当前状态 {member.state} 不可收发消息"
            )
