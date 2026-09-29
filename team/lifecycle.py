"""TeamAgent runtime 与 execution wrapper 的生命周期入口。"""

from collections.abc import Callable
from pathlib import Path
import re
from threading import RLock

from builtin.memory import MemoryMode, MemoryPolicy
from core.runtime import AgentRuntime, RunPolicy, RuntimeFactory, state
from event.interaction import NonInteractiveInteraction
from event.sink import NullEventSink
from tools.tool_handler import STANDARD_TOOLS_HANDLERS, STANDARD_TOOLS_LIST
from tools.task_system import TaskStore

from .agent import TeamAgent
from .contracts import (
    MemberEvent,
    MemberRecord,
    MessageUnavailableError,
    SpawnError,
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
