""" Agent 的顶层入口 Modules.

该顶层入口 Modules 告知用户系统信息，获取用户输入，执行 UserPromptSubmit hook，
执行 agent loop 工作循环（模型输出由 agent loop 工作循环处理），执行系统输出。

Typical usage example:
    import core.agent as agent
    agent()
"""

from dataclasses import dataclass, field
from typing import List, Dict
from uuid import uuid4

import builtin
import tools
import config
import event
from .runtime import AgentRuntime, RunPolicy, state, RuntimeFactory
from .session_driver import SessionDriver
from builtin.memory import MemoryPolicy, MemoryMode
from cli.event_sink import CliEventSink
from cli.cli_interaction import CliInteraction
from event.sink import EventSink
from event.sink import SynchronizedEventSink
from event.interaction import Interaction
from team.coordinator import TeamCoordinator
from team.factory import create_teammate_runtime
from tools.task_system import bind_task_handlers
from tools.team import (
    TEAM_COMMON_TOOLS,
    TEAM_LEAD_TOOLS,
    bind_team_handlers,
)


BASE_MASTER_PROMPT = "你是一个编码助手"


TEAM_LEAD_PROMPT = """
你是 Agent Team 的 lead。

Agent Team 协作规则：
1. 适合独立并行执行的任务，应先创建共享 task。
2. 无依赖任务可以分别交给多个 teammate。
3. 先完成所有需要的 spawn，再等待结果。
4. 等待 teammate 时使用 wait_teammates。
5. wait_teammates 会挂起当前 run，直到收到对应结果；它不会轮询，也不会消耗等待期间的 LLM token。
6. 禁止通过 read_messages、list_team、list_tasks 反复查询 teammate 是否完成。
7. read_messages 和 list_team 仅用于主动检查或诊断，不是同步机制。
8. 收到 <team-notification> 后，根据其中的 result 继续当前任务。
9. 如果 notification 表示 timeout，应决定继续等待、检查失败原因或使用已有结果，不要无限重试。
""".strip()


@dataclass
class MasterSession:
    """持有 lead Runtime 与 session-scoped TeamCoordinator。

    Args:
        runtime: 当前 CLI 会话的 lead Runtime。
        team: 当前会话独享的 TeamCoordinator。
    """

    runtime: AgentRuntime
    team: TeamCoordinator
    _closed: bool = field(default=False, init=False, repr=False)

    def close(self) -> None:
        """幂等关闭 TeamCoordinator 管理的全部 Worker。"""

        if self._closed:
            return
        self._closed = True
        self.team.shutdown_all(timeout_seconds=5.0)



def create_master_runtime(history: List, 
                          context: Dict,
                          events: EventSink,
                          interaction: Interaction,
                          team: TeamCoordinator | None = None,
                          session_id: str | None = None,
                        ):
    """ 创建主 Agent 的运行时环境。

    Args:
        history: lead 初始消息历史。
        context: lead 初始运行上下文。
        events: Runtime 使用的 EventSink。
        interaction: Runtime 使用的用户交互实现。
        team: 可选的 session-scoped TeamCoordinator。
        session_id: 可选的显式 session ID。

    Returns:
        AgentRuntime: 主 Agent 的运行时环境。
    """
        # 配置 queryLoop 循环的 RunPolicy
    configured_model = dict(config.Config().get_model_config())
    fallback_model = dict(configured_model)
    fallback_model["model_name"] = (
        configured_model.get("fallback_model_name")
        or configured_model["model_name"]
    )
    content_config = config.Config().get_content_length()
    tool_definitions = list(tools.TOOLS_LIST)
    tool_handlers = dict(tools.TOOLS_HANDLERS)
    master_prompt = BASE_MASTER_PROMPT
    if team is not None:
        # master session 中所有 task 工具都绑定到 team-scoped TaskStore。
        tool_definitions += TEAM_COMMON_TOOLS + TEAM_LEAD_TOOLS
        tool_handlers |= bind_task_handlers(team.tasks)
        tool_handlers |= bind_team_handlers(team, allow_lead_tools=True)
        master_prompt += "\n\n" + TEAM_LEAD_PROMPT

    agent_RunPolicy = RunPolicy(max_turns = 300,
                                prompt = master_prompt,
                                model = configured_model,
                                fallback_model = fallback_model,
                                tools_list = tool_definitions,
                                tool_handler = tool_handlers,
                                can_ask_user = True)
            
    # 初始化 queryLoop 循环的运行状态
    agent_state = state(messages = history, 
                                context = context, 
                                max_output_tokens = content_config["MAIN_OUTPUT_TOKENS"],
                                toolUse_prompt = "",
                                turn_count = 0,
                                transition = "", 
                                max_output_tokens_override = False,
                                recovery_count = 0,
                                has_attempted_reactive_compact = False,
                                current_model = agent_RunPolicy.model,
                                consecutive_529 = 0 )

    memoryPolicy = MemoryPolicy(
        mode = MemoryMode.READ_WRITE,
        namespace = "master",
    )

    runtime = RuntimeFactory.create(
        # Team Runtime 直接使用协议名称 lead，避免维护额外身份映射。
        agent_name = "lead" if team is not None else "Master Agent",
        policy = agent_RunPolicy,
        state = agent_state,
        memory_policy = memoryPolicy,
        workspace = config.Config().get_path_config("project_path"),
        session_id = session_id,
        events = events,
        interaction = interaction,
    )
    
    return runtime


def create_master_session(
    history: List,
    context: Dict,
    events: EventSink,
    interaction: Interaction,
) -> MasterSession:
    """创建带 Agent Teams 协作平面的 master session。

    Args:
        history: lead 初始消息历史。
        context: lead 初始运行上下文。
        events: 上层提供的 EventSink。
        interaction: 上层提供的用户输入和审批实现。

    Returns:
        MasterSession: 包含 lead Runtime 和 TeamCoordinator 的生命周期对象。
    """

    current_config = config.Config()
    workspace = current_config.get_path_config("project_path")
    session_id = uuid4().hex[:8]
    synchronized_events = SynchronizedEventSink(events)
    coordinator = TeamCoordinator(
        team_id=f"team_{session_id}",
        workspace=workspace,
        runtime_factory=create_teammate_runtime,
        max_members=current_config.get_team_config()["MAX_MEMBERS"],
    )
    runtime = create_master_runtime(
        history,
        context,
        events=synchronized_events,
        interaction=interaction,
        team=coordinator,
        session_id=session_id,
    )
    coordinator.bind_lead(runtime)
    return MasterSession(runtime=runtime, team=coordinator)


def master_agent():
    """ 主 Agent 的顶层入口 object.

    该顶层入口 object 告知用户系统信息，获取用户输入，执行 UserPromptSubmit hook，
    执行 agent loop 工作循环（模型输出由 agent loop 工作循环处理），执行系统输出。

    Args:
        None

    Returns:
        None
        
    Raises:
        None
    """

    # 初始化历史记录
    history = []
    # 初始化上下文
    context = builtin.update_context({})

    session = create_master_session(
        history,
        context,
        events=CliEventSink(),
        interaction=CliInteraction(),
    )
    runtime = session.runtime
    driver = SessionDriver(runtime=runtime, team=session.team)

    try:
        # 告知用户系统信息。该事件也位于 finally 保护范围内。
        runtime.events.emit(
            event.make_event(
                    runtime,
                    event.EventType.SYSTEM_MESSAGE,
                    trigger="输入问题，回车发送。输入 q 退出。",
                )
        )

        while True:
            # 获取用户输入
            try:
                user_input = runtime.interaction.get_user_input()

            except (EOFError, KeyboardInterrupt):
                break
            normalized_input = user_input.strip().lower()
            if not normalized_input or normalized_input in ("q", "exit"):
                break

            # 通过统一入口执行完整 run，避免顶层 Agent 重复维护 Hook 和状态初始化。
            agent_state, status = driver.submit(user_input)

            # 更新上下文
            history = agent_state.messages
            context = builtin.update_context(context, memory_index=runtime.memory.index_path)

            # 执行系统输出
            response = next(
                (
                    message.get("content")
                    for message in reversed(history)
                    if message.get("role") == "assistant"
                ),
                "",
            )
            if isinstance(response, list):
                for block in response:
                    block_type = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
                    if block_type == "text":
                        # 执行系统输出
                        text = block.get("text", "") if isinstance(block, dict) else block.text
                        runtime.events.emit(
                            event.make_event(
                                runtime,
                                event.EventType.ASSISTANT_MESSAGE,
                                text = text,
                            )
                        )
    finally:
        # 无论 CLI 正常退出、输入中断还是 run 抛错，都回收后台 teammate。
        session.close()
