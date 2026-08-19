""" 定义 agent 运行时的结构 """

from dataclasses import dataclass, field
from typing import List, Dict
from pathlib import Path
from uuid import uuid4

from builtin.memory import MemoryManager, MemoryPolicy
from builtin.artifacts import ArtifactStore
from tools.tool_handler import ToolExecutor
from builtin.load_prompt import PromptBuilder
from hook.hook_handler import HookManager, create_default_hooks
from event.sink import EventSink, NullEventSink
from event.interaction import Interaction, NonInteractiveInteraction



@dataclass()
class RunPolicy():
    """ 用于配置 queryLoop 循环的参数

    所有的 Agent 共用的通用 queryLoop 循环结构，
    通过配置 queryLoop 的 RunPolicy 中参数的不同
    得到不同种类的 Agent，该参数在循环中不改变。

    参数包括：
    - max_turns: 最大循环次数
    - prompt: 系统提示词、用户提示词（静态提示词）
    - model: 调用的模型
    - fallback_model: 失败时调用的模型
    - tools_list: 可以使用的工具的列表
    - can_ask_user: 是否可以询问用户问题
    """
    max_turns: int = 300
    prompt: str = ""
    model: Dict = field(default_factory=dict)
    fallback_model: Dict = field(default_factory=dict)
    tools_list: List = field(default_factory=list)
    tool_handler: Dict = field(default_factory=dict)
    can_ask_user: bool = False


@dataclass()
class state():
    """ 用于记录 queryLoop 循环的运行状态，该参数在循环中会改变。

    一个 Agent 的运行状态通过 state 中的参数进行记录，
    这些参数随着 queryLoop 循环的进行而改变。

    参数包括：
    - messages: 对话消息列表
    - context: 上下文参数，用于存储会话中的记忆、系统状态等信息
    - max_output_tokens: 最大输出token数
    - toolUse_prompt: 工具调用提示词（动态提示词）
    - turn_count: 当前循环次数计数
    - transition: 上次循环迭代的原因
    - max_output_tokens_override: 是否覆盖最大输出token数
    - recovery_count: 最大输出token数恢复次数
    - has_attempted_reactive_compact: 是否尝试过 reactive compact 模式
    - current_model: 当前使用的模型
    - consecutive_529: 连续出现 529 错误的次数
    """
    messages: List = field(default_factory=list)
    context: Dict = field(default_factory=dict)
    max_output_tokens: int = 4096
    toolUse_prompt: str = ""
    turn_count: int = 0
    transition: str = ""
    max_output_tokens_override: bool = False
    recovery_count: int = 3
    has_attempted_reactive_compact: bool = False
    current_model: Dict = field(default_factory=dict)
    consecutive_529: int = 0


@dataclass
class RuntimePaths:
    """ 用于记录 agent 运行时的路径
    """
    workspace: Path

    session_dir: Path
    agent_dir: Path

    tool_result_dir: Path
    transcript_dir: Path

    @classmethod
    def create(
        cls,
        workspace: Path,
        session_id: str,
        agent_id: str,
    ) -> "RuntimePaths":

        session_dir = workspace / ".agents" / "runs" / session_id
        agent_dir = session_dir / agent_id

        paths = cls(
            workspace=workspace,
            session_dir=session_dir,
            agent_dir=agent_dir,
            tool_result_dir=agent_dir / "tool_results",
            transcript_dir=agent_dir / "transcripts",
        )

        paths.agent_dir.mkdir(parents=True, exist_ok=True)

        return paths


@dataclass
class AgentRuntime:
    session_id: str
    agent_name: str
    agent_id: str

    policy: RunPolicy
    state: state

    paths: RuntimePaths

    prompt: PromptBuilder
    memory: MemoryManager
    artifacts: ArtifactStore

    hooks: HookManager
    events: EventSink
    tools: ToolExecutor

    interaction: Interaction

    def begin_run(self):
        self.state.turn_count = 0
        self.state.max_output_tokens_override = False
        self.state.has_attempted_reactive_compact = False
        self.state.recovery_count = 0
        self.state.consecutive_529 = 0



@dataclass
class RuntimeFactory:

    @staticmethod
    def create(
        *,
        agent_name: str,
        policy,
        state,
        memory_policy: MemoryPolicy,
        workspace: Path,
        session_id: str | None = None,
        hooks: HookManager | None = None,
        events: EventSink | None = None,
        interaction: Interaction | None = None,
    ) -> AgentRuntime:

        session_id = session_id or uuid4().hex[:8]
        agent_id = f"{agent_name}-{uuid4().hex[:8]}"

        paths = RuntimePaths.create(
            workspace=workspace,
            session_id=session_id,
            agent_id=agent_id,
        )

        memory_root = (
            workspace / ".agents" / ".memory" / memory_policy.namespace
        )

        prompt = PromptBuilder()

        memory = MemoryManager(
            root = memory_root,
            policy = memory_policy,
        )

        artifacts = ArtifactStore(
            tool_result_dir = paths.tool_result_dir,
            transcript_dir = paths.transcript_dir,
        )

        if hooks is None:
            hooks = create_default_hooks()

        if events is None:
            events = NullEventSink()

        tools = ToolExecutor(
            registry = policy.tool_handler,
            allowed_tools = policy.tools_list,
            workspace = workspace,
        )

        if interaction is None:
            interaction = NonInteractiveInteraction()
        
        return AgentRuntime(
            session_id = session_id,
            agent_name = agent_name,
            agent_id = agent_id,
            policy = policy,
            state = state,
            paths = paths,
            prompt = prompt,
            memory = memory,
            artifacts = artifacts,
            hooks = hooks,
            events = events,
            tools = tools,
            interaction = interaction,
        )
