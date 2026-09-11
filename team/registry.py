"""Team member metadata 与 MemberState 的唯一 owner。"""

from dataclasses import replace
from threading import RLock

from .contracts import (
    DuplicateMemberError,
    InvalidMemberTransitionError,
    MemberEvent,
    MemberNotFoundError,
    MemberRecord,
    MemberState,
    TeamError,
    TransitionSource,
    UnauthorizedMemberOperationError,
    UnregisterReason,
)


_TRANSITIONS = {
    (MemberState.STARTING, MemberEvent.SPAWN_SUCCESS): MemberState.IDLE,
    (MemberState.IDLE, MemberEvent.TASK_CLAIMED): MemberState.BUSY,
    (MemberState.BUSY, MemberEvent.DEPENDENCY_WAIT): MemberState.WAITING,
    (MemberState.WAITING, MemberEvent.DEPENDENCY_RESOLVED): MemberState.BUSY,
    (MemberState.BUSY, MemberEvent.TASK_FINISHED): MemberState.IDLE,
    (MemberState.IDLE, MemberEvent.SHUTDOWN): MemberState.STOPPED,
    (MemberState.BUSY, MemberEvent.SHUTDOWN): MemberState.STOPPED,
    (MemberState.WAITING, MemberEvent.SHUTDOWN): MemberState.STOPPED,
    (MemberState.STOPPED, MemberEvent.SHUTDOWN): MemberState.STOPPED,
    (MemberState.FAILED, MemberEvent.SHUTDOWN): MemberState.FAILED,
    (MemberState.IDLE, MemberEvent.FATAL_RUNTIME_ERROR): MemberState.FAILED,
    (MemberState.BUSY, MemberEvent.FATAL_RUNTIME_ERROR): MemberState.FAILED,
    (MemberState.WAITING, MemberEvent.FATAL_RUNTIME_ERROR): MemberState.FAILED,
}

_AUTHORIZED_SOURCES = {
    MemberEvent.SPAWN_SUCCESS: frozenset({TransitionSource.LIFECYCLE_MANAGER}),
    MemberEvent.TASK_CLAIMED: frozenset({TransitionSource.TEAM_COORDINATOR}),
    MemberEvent.DEPENDENCY_WAIT: frozenset({TransitionSource.TEAM_AGENT}),
    MemberEvent.DEPENDENCY_RESOLVED: frozenset(
        {TransitionSource.TASK_STORE, TransitionSource.TEAM_COORDINATOR}
    ),
    MemberEvent.TASK_FINISHED: frozenset({TransitionSource.TEAM_AGENT}),
    MemberEvent.SHUTDOWN: frozenset(
        {
            TransitionSource.TEAM_COORDINATOR,
            TransitionSource.LIFECYCLE_MANAGER,
        }
    ),
    MemberEvent.FATAL_RUNTIME_ERROR: frozenset(
        {
            TransitionSource.LIFECYCLE_MANAGER,
            TransitionSource.RUNTIME_SUPERVISOR,
        }
    ),
}


def _required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TeamError(f"{field_name} 必须是非空字符串")
    return value.strip()


class MemberRegistry:
    """原子维护一支 team 的 immutable member records。"""

    def __init__(self):
        self._members: dict[str, MemberRecord] = {}
        self._lock = RLock()

    def register(self, agent_id: str, agent_name: str) -> MemberRecord:
        """注册一个 STARTING member，并返回其 immutable snapshot。"""

        agent_id = _required_text(agent_id, "agent_id")
        agent_name = _required_text(agent_name, "agent_name")
        with self._lock:
            if agent_id in self._members:
                raise DuplicateMemberError(f"member {agent_id!r} 已存在")
            member = MemberRecord(
                agent_id=agent_id,
                agent_name=agent_name,
                state=MemberState.STARTING,
            )
            self._members[agent_id] = member
            return member

    def unregister(
        self,
        agent_id: str,
        *,
        reason: UnregisterReason,
    ) -> MemberRecord | None:
        """仅在 spawn rollback 或 TeamRuntime 最终释放时删除记录。"""

        agent_id = _required_text(agent_id, "agent_id")
        try:
            reason = UnregisterReason(reason)
        except (TypeError, ValueError) as exc:
            raise UnauthorizedMemberOperationError(
                f"不允许的 unregister reason: {reason!r}"
            ) from exc

        with self._lock:
            member = self._members.get(agent_id)
            if member is None:
                return None
            if (
                reason is UnregisterReason.SPAWN_ROLLBACK
                and member.state is not MemberState.STARTING
            ):
                raise UnauthorizedMemberOperationError(
                    "spawn rollback 只能删除 STARTING member"
                )
            return self._members.pop(agent_id)

    def get(self, agent_id: str) -> MemberRecord:
        """返回指定 member 的 immutable snapshot。"""

        agent_id = _required_text(agent_id, "agent_id")
        with self._lock:
            try:
                return self._members[agent_id]
            except KeyError as exc:
                raise MemberNotFoundError(f"member {agent_id!r} 不存在") from exc

    def get_member_state(self, agent_id: str) -> MemberState:
        """返回指定 member 的当前状态。"""

        return self.get(agent_id).state

    def list(self) -> tuple[MemberRecord, ...]:
        """按注册顺序返回所有 immutable member snapshots。"""

        with self._lock:
            return tuple(self._members.values())

    def transition(
        self,
        agent_id: str,
        event: MemberEvent,
        *,
        source: TransitionSource,
    ) -> MemberRecord:
        """校验来源与状态机，并原子地应用一次 MemberState transition。"""

        agent_id = _required_text(agent_id, "agent_id")
        try:
            event = MemberEvent(event)
        except (TypeError, ValueError) as exc:
            raise InvalidMemberTransitionError(
                f"未知 member event: {event!r}"
            ) from exc
        try:
            source = TransitionSource(source)
        except (TypeError, ValueError) as exc:
            raise UnauthorizedMemberOperationError(
                f"未知 transition source: {source!r}"
            ) from exc

        with self._lock:
            member = self._members.get(agent_id)
            if member is None:
                raise MemberNotFoundError(f"member {agent_id!r} 不存在")
            if source not in _AUTHORIZED_SOURCES[event]:
                raise UnauthorizedMemberOperationError(
                    f"{source} 无权提交 {event}"
                )
            next_state = _TRANSITIONS.get((member.state, event))
            if next_state is None:
                raise InvalidMemberTransitionError(
                    f"不允许 {member.state} --{event}--> transition"
                )
            updated = replace(member, state=next_state)
            self._members[agent_id] = updated
            return updated
