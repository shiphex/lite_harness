"""TeamAgent runtime 与 execution wrapper 的生命周期入口。"""

from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
import re
from threading import Lock, RLock

from builtin.memory import MemoryMode, MemoryPolicy
from core.runtime import AgentRuntime, RunPolicy, RuntimeFactory, state
from event.interaction import NonInteractiveInteraction
from event.sink import NullEventSink
from tools.tool_handler import STANDARD_TOOLS_HANDLERS, STANDARD_TOOLS_LIST
from tools.task_system import TaskStore, list_tasks

from .agent import TeamAgent
from .contracts import (
    MemberEvent,
    MemberRecord,
    MessageUnavailableError,
    MemberState,
    SpawnError,
    StopBusyError,
    StopPendingTaskError,
    TeamError,
    TransitionSource,
    UnregisterReason,
)
from .registry import MemberRegistry
from .messaging import MessageBus
from .messaging_tools import TEAM_AGENT_MESSAGE_TOOLS, bind_message_handlers
from .task_tools import TEAM_AGENT_TASK_TOOLS, bind_task_handlers


_AGENT_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")
_TEAM_TOOL_NAMES = frozenset(
    {"read_file", "glob", "load_skill", "bash", "write_file", "edit_file"}
)


def _team_agent_tools() -> tuple[list[dict], dict]:
    definitions = [
        dict(tool)
        for tool in STANDARD_TOOLS_LIST
        if tool.get("name") in _TEAM_TOOL_NAMES
    ]
    for definition in definitions:
        if definition["name"] == "bash":
            definition["input_schema"] = {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
                "additionalProperties": False,
            }
    handlers = {
        name: STANDARD_TOOLS_HANDLERS[name]
        for name in _TEAM_TOOL_NAMES
    }
    return definitions, handlers


class LifecycleManager:
    """创建并持有 TeamAgent；后台 worker 行为留给后续 phase。"""

    def __init__(
        self,
        *,
        member_registry: MemberRegistry,
        message_bus: MessageBus | None = None,
        runtime_factory: type[RuntimeFactory] = RuntimeFactory,
        session_id: str | None = None,
        agent_factory: Callable[..., TeamAgent] = TeamAgent,
        task_store: TaskStore | None = None,
    ):
        self.member_registry = member_registry
        self.message_bus = message_bus if message_bus is not None else MessageBus(member_registry)
        self.runtime_factory = runtime_factory
        self.session_id = session_id
        self.agent_factory = agent_factory
        self.task_store = task_store
        self._agents: dict[str, TeamAgent] = {}
        self._execution_locks: dict[str, Lock] = {}
        self._fatal_errors: dict[str, str] = {}
        self._released_result: dict | None = None
        self._lock = RLock()

    def spawn(
        self,
        *,
        parent_runtime: AgentRuntime,
        agent_name: str,
    ) -> MemberRecord:
        """创建 TeamAgent，并以 STARTING → IDLE 作为发布事务。"""

        agent_name = self._validate_spawn_request(parent_runtime, agent_name)
        runtime: AgentRuntime | None = None
        registered = False
        stage = "runtime creation"

        with self._lock:
            if self._released_result is not None:
                raise SpawnError("TeamRuntime 已最终释放")
            try:
                runtime = self._create_runtime(parent_runtime, agent_name)

                stage = "TeamAgent wrapper creation"
                agent = self.agent_factory(
                    runtime=runtime,
                    mailbox_handle=self.message_bus.bind(runtime.agent_id),
                )

                stage = "member registration"
                self.member_registry.register(runtime.agent_id, runtime.agent_name)
                registered = True

                stage = "lifecycle publication"
                self._agents[runtime.agent_id] = agent

                stage = "member commit"
                return self.member_registry.transition(
                    runtime.agent_id,
                    MemberEvent.SPAWN_SUCCESS,
                    source=TransitionSource.LIFECYCLE_MANAGER,
                )
            except Exception as exc:
                rollback_error = self._rollback_unpublished(runtime, registered)
                if rollback_error is not None:
                    raise SpawnError(
                        f"spawn 在 {stage} 失败，且 rollback 失败: {rollback_error}"
                    ) from exc
                if isinstance(exc, SpawnError):
                    raise
                raise SpawnError(f"spawn 在 {stage} 失败: {exc}") from exc

    def get_agent(self, agent_id: str) -> TeamAgent:
        """查询 LifecycleManager 当前持有的 TeamAgent，不转移 ownership。"""

        with self._lock:
            try:
                return self._agents[agent_id]
            except (KeyError, TypeError) as exc:
                raise MessageUnavailableError(f"TeamAgent {agent_id!r} 不存在") from exc

    def ensure_open(self) -> None:
        with self._lock:
            if self._released_result is not None:
                raise MessageUnavailableError("TeamRuntime 已最终释放")

    @contextmanager
    def operation(self):
        """使简短团队操作与最终释放互斥。"""
        with self._lock:
            self.ensure_open()
            yield

    def shutdown(self, agent_id: str) -> MemberRecord:
        """停止已发布的 TeamAgent，保留可查询的终态 record。"""
        lock = self._execution_lock(agent_id)
        if not lock.acquire(blocking=False):
            raise StopBusyError(f"TeamAgent {agent_id!r} 正在执行")
        try:
            with self._lock:
                if self._released_result is not None:
                    raise MessageUnavailableError("TeamRuntime 已最终释放")
                member = self.member_registry.get(agent_id)
                unfinished = (
                    tuple(
                        task.id
                        for task in list_tasks(store=self.task_store)
                        if task.owner == agent_id and task.status == "in_progress"
                    )
                    if self.task_store is not None else ()
                )
                if member.state in {MemberState.STOPPED, MemberState.FAILED}:
                    if unfinished:
                        raise StopPendingTaskError(
                            f"TeamAgent {agent_id!r} 已进入 {member.state}，仍持有未完成任务 {unfinished}"
                        )
                    return member
                self.get_agent(agent_id)
                if unfinished or member.state is not MemberState.IDLE:
                    raise StopPendingTaskError(
                        f"TeamAgent {agent_id!r} 待恢复任务={unfinished}, 成员状态={member.state}"
                    )
                with self.message_bus.state_change_guard():
                    stopped = self.member_registry.transition(
                        agent_id,
                        MemberEvent.SHUTDOWN,
                        source=TransitionSource.LIFECYCLE_MANAGER,
                    )
                self._agents.pop(agent_id, None)
                return stopped
        finally:
            lock.release()

    def _execution_lock(self, agent_id: str) -> Lock:
        with self._lock:
            return self._execution_locks.setdefault(agent_id, Lock())

    @contextmanager
    def execution(self, agent_id: str):
        """排他地使用一个已发布的 TeamAgent。"""
        lock = self._execution_lock(agent_id)
        if not lock.acquire(blocking=False):
            raise StopBusyError(f"TeamAgent {agent_id!r} 正在执行另一轮任务")
        try:
            yield self.get_agent(agent_id)
        finally:
            lock.release()

    def report_fatal(self, agent_id: str, error: str) -> dict:
        """显式报告不可恢复故障；普通任务执行异常不进入此入口。"""
        if not isinstance(error, str) or not error.strip():
            raise TeamError("fatal error 必须是非空文本")
        lock = self._execution_lock(agent_id)
        if not lock.acquire(blocking=False):
            raise StopBusyError(f"TeamAgent {agent_id!r} 正在执行")
        try:
            with self._lock:
                if self._released_result is not None:
                    raise MessageUnavailableError("TeamRuntime 已最终释放")
                member = self.member_registry.get(agent_id)
                if member.state is not MemberState.FAILED:
                    self.get_agent(agent_id)
                    with self.message_bus.state_change_guard():
                        member = self.member_registry.transition(
                            agent_id,
                            MemberEvent.FATAL_RUNTIME_ERROR,
                            source=TransitionSource.LIFECYCLE_MANAGER,
                        )
                    self._fatal_errors[agent_id] = error.strip()
                    self._agents.pop(agent_id, None)
                else:
                    self._fatal_errors.setdefault(agent_id, error.strip())
                return self.member_status(agent_id)
        finally:
            lock.release()

    def member_status(self, agent_id: str) -> dict:
        with self._lock:
            member = self.member_registry.get(agent_id)
            tasks = [
                task.id for task in list_tasks(store=self.task_store)
                if task.owner == agent_id
            ] if self.task_store is not None else []
            return {
                "agent_id": member.agent_id,
                "member_state": member.state,
                "error": self._fatal_errors.get(agent_id),
                "task_ids": tasks,
            }

    def teardown(self) -> dict:
        """逐成员安全停止，只有全部成功后才最终释放内存状态。"""
        with self._lock:
            if self._released_result is not None:
                return self._released_result
            stopped = []
            failed = []
            failures = {}
            for member in self.member_registry.list():
                try:
                    terminal = self.shutdown(member.agent_id)
                    if terminal.state is MemberState.STOPPED:
                        stopped.append(member.agent_id)
                    else:
                        failed.append(member.agent_id)
                except Exception as exc:
                    failures[member.agent_id] = {
                        "type": type(exc).__name__, "message": str(exc)
                    }
            if failures:
                return {"status": "partial", "released": False,
                        "stopped": stopped, "failed": failed, "failures": failures}
            try:
                with self.message_bus.state_change_guard():
                    snapshot = self.message_bus.snapshot_mailboxes()
                    try:
                        self.message_bus.release()
                        self.member_registry.release_all(reason=UnregisterReason.TEAM_RELEASE)
                    except Exception:
                        self.message_bus.restore_mailboxes(snapshot)
                        raise
            except Exception as exc:
                return {"status": "partial", "released": False,
                        "stopped": stopped, "failed": failed,
                        "failures": {"release": {"type": type(exc).__name__, "message": str(exc)}}}
            self._execution_locks.clear()
            self._agents.clear()
            self._fatal_errors.clear()
            self._released_result = {
                "status": "released", "released": True,
                "stopped": stopped, "failed": failed, "failures": {},
            }
            return self._released_result

    def _validate_spawn_request(
        self,
        parent_runtime: AgentRuntime,
        agent_name: str,
    ) -> str:
        if not isinstance(agent_name, str) or _AGENT_NAME.fullmatch(agent_name) is None:
            raise SpawnError(
                "agent_name 必须匹配 ^[A-Za-z][A-Za-z0-9_-]{0,31}$"
            )
        if self.session_id is not None and parent_runtime.session_id != self.session_id:
            raise SpawnError("parent runtime 不属于当前 TeamRuntime session")
        return agent_name

    def _create_runtime(
        self,
        parent_runtime: AgentRuntime,
        agent_name: str,
    ) -> AgentRuntime:
        tool_definitions, tool_handlers = _team_agent_tools()
        tool_definitions.extend(dict(tool) for tool in TEAM_AGENT_MESSAGE_TOOLS)
        tool_handlers.update(bind_message_handlers(self.get_agent))
        if self.task_store is not None:
            tool_definitions.extend(dict(tool) for tool in TEAM_AGENT_TASK_TOOLS)
            tool_handlers.update(
                bind_task_handlers(
                    self.get_agent, self.member_registry, self.task_store
                )
            )
        model = dict(parent_runtime.policy.model)
        fallback_model = dict(parent_runtime.policy.fallback_model)
        policy = RunPolicy(
            max_turns=30,
            prompt=f"你是 Agent Team 中的 TeamAgent：{agent_name}。",
            model=model,
            fallback_model=fallback_model,
            tools_list=tool_definitions,
            tool_handler=tool_handlers,
            can_ask_user=False,
            allow_background_tools=False,
        )
        agent_state = state(
            messages=[],
            context={},
            max_output_tokens=parent_runtime.state.max_output_tokens,
            current_model=dict(model),
            recovery_count=0,
        )
        return self.runtime_factory.create(
            agent_name=agent_name,
            policy=policy,
            state=agent_state,
            memory_policy=MemoryPolicy(
                mode=MemoryMode.READ_ONLY,
                namespace="master",
            ),
            workspace=Path(parent_runtime.paths.workspace),
            session_id=parent_runtime.session_id,
            events=NullEventSink(),
            interaction=NonInteractiveInteraction(),
        )

    def _rollback_unpublished(
        self,
        runtime: AgentRuntime | None,
        registered: bool,
    ) -> Exception | None:
        if runtime is None:
            return None
        self._agents.pop(runtime.agent_id, None)
        if not registered:
            return None
        try:
            self.member_registry.unregister(
                runtime.agent_id,
                reason=UnregisterReason.SPAWN_ROLLBACK,
            )
        except Exception as exc:
            return exc
        return None
