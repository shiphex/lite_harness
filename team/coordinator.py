"""Agent Teams 协作平面的轻量 Coordinator。

TeamCoordinator 维护 team-scoped TaskStore、成员 roster、Worker 和 MessageBus。
它不调用模型、不执行工具，也不实现 Agent Loop；所有推理仍由 teammate 自己的
``AgentRuntime`` 完成。
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path
import re
import inspect
from threading import RLock
from time import monotonic
from typing import TYPE_CHECKING, Callable

import event
from tools.task_system import TaskStore

from .bus import MessageBus
from .contract import MemberStatus, TeamMember, TeamMessage, TeammateProfile
from .worker import TeammateWorker
from .worktree import WorktreeHandle, WorktreeManager


if TYPE_CHECKING:
    from core.runtime import AgentRuntime


TEAMMATE_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")
TERMINAL_STATUSES = {MemberStatus.STOPPED, MemberStatus.FAILED}
ACTIVE_STATUSES = {
    MemberStatus.STARTING,
    MemberStatus.WORKING,
    MemberStatus.IDLE,
    MemberStatus.STOPPING,
}


class TeamError(ValueError):
    """可预期的 Agent Teams 协作错误。"""


class TeamPermissionError(TeamError):
    """Runtime 不具备当前 TeamCoordinator 操作权限时抛出。"""


class TeamCoordinator:
    """管理单个 lead session 内的 Agent Team。"""

    def __init__(
        self,
        *,
        team_id: str,
        workspace: Path,
        runtime_factory: Callable,
        max_members: int = 3,
    ):
        """初始化 TeamCoordinator。

        Args:
            team_id: 当前 team 的唯一 ID。
            workspace: lead Runtime 的项目工作目录。
            runtime_factory: 创建普通 teammate AgentRuntime 的函数。
            max_members: 允许同时存在的最大活跃 teammate 数量。

        Raises:
            ValueError: max_members 不是正整数时抛出。
        """

        if not isinstance(max_members, int) or max_members <= 0:
            raise ValueError("max_members 必须是正整数")

        self.team_id = team_id
        self.workspace = Path(workspace).resolve()
        self.team_dir = self.workspace / ".agents" / "teams" / team_id
        # Team session 中的每个 owner 同时只能推进一个 active task；普通
        # TaskStore 不配置这一策略，因而保持原有的通用任务语义。
        self.tasks = TaskStore(
            self.team_dir / "tasks",
            max_active_tasks_per_owner=1,
        )
        self.runtime_factory = runtime_factory
        self.max_members = max_members
        self.worktrees = WorktreeManager(
            repo_root=self.workspace,
            team_id=team_id,
        )
        self.member_worktrees: dict[str, WorktreeHandle] = {}

        self.bus = MessageBus()
        self.bus.register("lead")
        self.members: dict[str, TeamMember] = {}
        self.workers: dict[str, TeammateWorker] = {}
        # roster 与 Worker 生命周期共享同一把锁，避免维护额外 activity 状态。
        self._lock = RLock()
        self._session_id: str | None = None
        self._lead_agent_id: str | None = None
        self._lead_runtime: AgentRuntime | None = None

    def bind_lead(self, runtime: "AgentRuntime") -> None:
        """绑定当前 TeamCoordinator 的唯一 lead Runtime identity。

        Args:
            runtime: 当前 master session 创建完成后的 lead Runtime。

        Raises:
            TeamError: 当前 coordinator 已绑定 lead 时抛出。
        """

        with self._lock:
            if self._lead_agent_id is not None:
                raise TeamError("team lead 已绑定")
            self._session_id = runtime.session_id
            self._lead_agent_id = runtime.agent_id
            self._lead_runtime = runtime

    def spawn(
        self,
        *,
        parent_runtime: "AgentRuntime",
        name: str,
        role: str,
        prompt: str,
        profile: TeammateProfile = TeammateProfile.RESEARCHER,
    ) -> TeamMember:
        """创建并启动一个持久 teammate。

        task 的创建、认领与完成由 lead 和 teammate 通过共享 task 工具显式完成，
        spawn 只负责 Runtime 与 Worker 生命周期。

        Args:
            parent_runtime: 发起创建操作的 lead Runtime。
            name: team 内唯一的 teammate 名称。
            role: teammate 的职责说明。
            prompt: 首轮 assignment 内容。
            profile: teammate capability profile；默认只读 researcher。

        Returns:
            TeamMember: 已登记的 teammate 快照。

        Raises:
            TeamError: 调用方、名称或容量不符合要求时抛出。
            RuntimeError: Runtime 或 Worker 无法启动时抛出。
        """

        self._assert_lead(parent_runtime)
        self._validate_member_input(name, role, prompt)
        try:
            profile = TeammateProfile(profile)
        except ValueError as error:
            raise TeamError(f"未知 teammate profile: {profile!r}") from error

        worktree: WorktreeHandle | None = None

        with self._lock:
            # 终态成员保留在 roster 中，因此直接检查 roster 即可保证名称不复用。
            if name in self.members:
                raise TeamError(f"teammate name {name!r} 在当前 team 中已使用")
            if self._active_count_unlocked() >= self.max_members:
                raise TeamError(f"活跃 teammate 已达到上限 {self.max_members}")

            self.bus.register(name)
            try:
                if profile == TeammateProfile.WRITER:
                    worktree = self.worktrees.create(member=name, base_ref="HEAD")

                runtime = self._create_runtime(
                    parent_runtime=parent_runtime,
                    name=name,
                    role=role.strip(),
                    profile=profile,
                    workspace=worktree.path if worktree is not None else None,
                )
                if runtime.session_id != parent_runtime.session_id:
                    raise TeamError("teammate Runtime 必须属于当前 team session")
                if runtime.agent_id == parent_runtime.agent_id:
                    raise TeamError("teammate Runtime 必须拥有独立 agent_id")
                if any(
                    existing.agent_id == runtime.agent_id
                    for existing in self.members.values()
                ):
                    raise TeamError("teammate Runtime agent_id 在当前 team 中已使用")
                member = TeamMember(
                    name=name,
                    role=role.strip(),
                    agent_id=runtime.agent_id,
                    profile=profile,
                    workspace=(
                        str(worktree.path)
                        if worktree is not None
                        else None
                    ),
                    branch=worktree.branch if worktree is not None else None,
                )
                worker = TeammateWorker(
                    name=name,
                    runtime=runtime,
                    bus=self.bus,
                    on_status=self._set_status,
                )
                self.members[name] = member
                self.workers[name] = worker
                if worktree is not None:
                    self.member_worktrees[name] = worktree
            except Exception:
                # Runtime factory 失败时成员尚未对外可见，清除半成品 roster 与 mailbox。
                self.members.pop(name, None)
                self.workers.pop(name, None)
                self.member_worktrees.pop(name, None)
                self.bus.unregister(name)
                if worktree is not None:
                    self.worktrees.remove(worktree, discard=True)
                raise

        self._emit(
            parent_runtime,
            event.EventType.TEAM_MEMBER_SPAWNED,
            member=name,
            role=role.strip(),
            profile=profile,
            branch=worktree.branch if worktree is not None else None,
        )
        try:
            worker.start(prompt)
        except Exception:
            # spawned 已对外可见，因此线程启动失败应保留 terminal roster 记录。
            self._set_status(name, MemberStatus.FAILED)
            raise
        return replace(member)

    def _create_runtime(
        self,
        *,
        parent_runtime: "AgentRuntime",
        name: str,
        role: str,
        profile: TeammateProfile,
        workspace: Path | None,
    ):
        """调用新 runtime factory，并兼容旧版四参数测试工厂。"""

        kwargs = {
            "profile": profile,
            "workspace": workspace,
        }
        try:
            signature = inspect.signature(self.runtime_factory)
        except (TypeError, ValueError):
            signature = None

        if signature is not None:
            parameters = signature.parameters.values()
            accepts_kwargs = any(
                parameter.kind == inspect.Parameter.VAR_KEYWORD
                for parameter in parameters
            )
            if not accepts_kwargs:
                kwargs = {
                    key: value
                    for key, value in kwargs.items()
                    if key in signature.parameters
                }

        return self.runtime_factory(
            parent_runtime,
            self,
            name,
            role,
            **kwargs,
        )

    def send(
        self,
        runtime: "AgentRuntime",
        recipient: str,
        content: str,
    ) -> TeamMessage:
        """以当前 Runtime 的 team identity 发送单向消息。

        Args:
            runtime: 发起消息的 lead 或 teammate Runtime。
            recipient: 接收者 team name。
            content: 非空消息正文。

        Returns:
            TeamMessage: 已投递的消息。

        Raises:
            TeamError: 调用方、收件人或正文不合法时抛出。
        """

        sender = self._runtime_name(runtime)
        if not isinstance(content, str) or not content.strip():
            raise TeamError("team message content 不能为空")

        if recipient != "lead":
            with self._lock:
                member = self.members.get(recipient)
                if member is None:
                    raise TeamError(f"未知 teammate: {recipient}")
                if member.status in {
                    MemberStatus.STOPPING,
                    MemberStatus.STOPPED,
                    MemberStatus.FAILED,
                }:
                    raise TeamError(
                        f"teammate {recipient} 状态为 {member.status}，不能接收新消息"
                    )

        message = TeamMessage(
            sender=sender,
            recipient=recipient,
            content=content.strip(),
        )
        self.bus.send(message)
        self._emit_message(runtime, event.EventType.TEAM_MESSAGE_SENT, message)
        return message

    def read_messages(self, runtime: "AgentRuntime") -> list[TeamMessage]:
        """非阻塞读取并清空当前 Runtime 的 mailbox。

        Args:
            runtime: 需要读取消息的 lead 或 teammate Runtime。

        Returns:
            list[TeamMessage]: 按入队顺序排列的全部未读消息。

        Raises:
            TeamError: Runtime 不属于当前 team 时抛出。
        """

        name = self._runtime_name(runtime)
        messages = self.bus.drain(name)
        for message in messages:
            self._emit_message(
                runtime,
                event.EventType.TEAM_MESSAGE_RECEIVED,
                message,
            )
        return messages

    def list_members(self, runtime: "AgentRuntime") -> list[TeamMember]:
        """返回带动态 ``current_task`` 的 teammate 快照。

        Args:
            runtime: 请求当前 team roster 的 lead 或 teammate Runtime。

        Returns:
            list[TeamMember]: 按创建顺序排列的成员副本。
        """

        self._runtime_name(runtime)
        tasks = self.tasks.list()
        current_tasks = {}
        for task in tasks:
            if task.owner and task.status == "in_progress":
                current_tasks.setdefault(task.owner, task.id)
        with self._lock:
            return [
                replace(member, current_task=current_tasks.get(member.name))
                for member in self.members.values()
            ]

    def snapshot(self, runtime: "AgentRuntime") -> dict:
        """返回 roster 和 team-scoped task 的 JSON 友好快照。

        Args:
            runtime: 请求当前 team 快照的 lead 或 teammate Runtime。

        Returns:
            dict: 包含 team_id、members 和 tasks 的当前状态。
        """

        return {
            "team_id": self.team_id,
            "members": [asdict(member) for member in self.list_members(runtime)],
            "tasks": [asdict(task) for task in self.tasks.list()],
        }

    def shutdown(self, runtime: "AgentRuntime", name: str) -> bool:
        """请求指定 teammate 协作式停止。

        Args:
            runtime: 发起关闭的 lead Runtime。
            name: 需要关闭的 teammate 名称。

        Returns:
            bool: 新增关闭请求时返回 True；成员已结束时返回 False。

        Raises:
            TeamError: 非 lead 调用或 teammate 不存在时抛出。
        """

        self._assert_lead(runtime)
        with self._lock:
            member = self.members.get(name)
            worker = self.workers.get(name)
            if member is None or worker is None:
                raise TeamError(f"未知 teammate: {name}")
            if member.status in TERMINAL_STATUSES:
                return False

        self._set_status(name, MemberStatus.STOPPING)
        worker.stop()
        return True

    def shutdown_all(self, timeout_seconds: float = 5.0) -> list[str]:
        """停止全部 teammate，并在共享截止时间内等待线程退出。

        Args:
            timeout_seconds: 所有 Worker 共用的最大等待秒数。

        Returns:
            list[str]: 截止时间后仍在运行的 teammate 名称；正常停止时为空列表。
        """

        with self._lock:
            workers = list(self.workers.items())

        for name, worker in workers:
            with self._lock:
                member = self.members.get(name)
                terminal = member is None or member.status in TERMINAL_STATUSES
            if terminal:
                continue
            self._set_status(name, MemberStatus.STOPPING)
            try:
                worker.stop()
            except KeyError:
                # 仅可能出现在启动失败清理与关闭并发发生时，Worker 已无可唤醒 mailbox。
                pass

        deadline = monotonic() + max(0.0, timeout_seconds)
        for _, worker in workers:
            worker.join(max(0.0, deadline - monotonic()))

        alive = [name for name, worker in workers if worker.is_alive()]
        if alive:
            with self._lock:
                lead_runtime = self._lead_runtime
            if lead_runtime is not None:
                self._emit(
                    lead_runtime,
                    event.EventType.TEAM_MEMBER_SHUTDOWN_TIMEOUT,
                    members=alive,
                    timeout_seconds=timeout_seconds,
                )
        return alive

    def _runtime_name(self, runtime: "AgentRuntime") -> str:
        """校验 Runtime 的 session/agent identity 并返回其 team name。"""

        with self._lock:
            if self._session_id is None or self._lead_agent_id is None:
                raise TeamPermissionError("team lead 尚未绑定")
            if runtime.session_id != self._session_id:
                raise TeamPermissionError("当前 Runtime 不属于该 team session")
            if runtime.agent_id == self._lead_agent_id:
                return "lead"
            for member in self.members.values():
                if member.agent_id == runtime.agent_id:
                    return member.name
        raise TeamPermissionError("当前 Runtime 不属于该 team")

    def _assert_lead(self, runtime: "AgentRuntime") -> None:
        """校验调用 Runtime 是否为 team lead。"""

        if self._runtime_name(runtime) != "lead":
            raise TeamPermissionError("只有 team lead 可以执行该操作")

    def _validate_member_input(self, name: str, role: str, prompt: str) -> None:
        """校验 teammate identity 和 assignment 文本。"""

        if not isinstance(name, str) or TEAMMATE_NAME_RE.fullmatch(name) is None:
            raise TeamError(
                "teammate name 必须符合 ^[A-Za-z][A-Za-z0-9_-]{0,31}$"
            )
        if not isinstance(role, str) or not role.strip():
            raise TeamError("teammate role 不能为空")
        if not isinstance(prompt, str) or not prompt.strip():
            raise TeamError("teammate prompt 不能为空")

    def _active_count_unlocked(self) -> int:
        """在 Coordinator 锁内统计活跃 teammate。"""

        return sum(
            member.status in ACTIVE_STATUSES
            for member in self.members.values()
        )

    def _set_status(self, name: str, status: MemberStatus) -> None:
        """原子更新成员状态并发布状态事件。"""

        with self._lock:
            member = self.members.get(name)
            worker = self.workers.get(name)
            if member is None or worker is None:
                return
            # 终态不可逆；STOPPING 也不能被当前 run 尾部的 IDLE 覆盖。
            if member.status in TERMINAL_STATUSES:
                return
            if member.status == MemberStatus.STOPPING and status in {
                MemberStatus.WORKING,
                MemberStatus.IDLE,
            }:
                return
            if member.status == status:
                return
            member.status = status
            runtime = worker.runtime

        self._emit(
            runtime,
            event.EventType.TEAM_MEMBER_STATUS_CHANGED,
            member=name,
            status=status,
        )
        if status == MemberStatus.STOPPED:
            self._emit(
                runtime,
                event.EventType.TEAM_MEMBER_STOPPED,
                member=name,
            )

    @staticmethod
    def _emit_message(
        runtime: "AgentRuntime",
        event_type: event.EventType,
        message: TeamMessage,
    ) -> None:
        """使用消息字段发布 team message 事件。"""

        TeamCoordinator._emit(
            runtime,
            event_type,
            message_id=message.message_id,
            sender=message.sender,
            recipient=message.recipient,
            kind=message.kind,
        )

    @staticmethod
    def _emit(
        runtime: "AgentRuntime",
        event_type: event.EventType,
        **data,
    ) -> None:
        """使用指定 Runtime metadata 发布协作事件。"""

        runtime.events.emit(event.make_event(runtime, event_type, **data))
