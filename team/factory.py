"""teammate AgentRuntime 工厂。

teammate 不是新的 Runtime 类型，而是普通 ``AgentRuntime`` 的受限配置：独立 history、
只读 memory、非交互审批和最小只读工具集。所有 teammate 仍执行统一 query loop。
"""

from builtin.memory import MemoryMode, MemoryPolicy
from core.runtime import RunPolicy, RuntimeFactory, state
from event.interaction import NonInteractiveInteraction
from tools.task_system import bind_task_handlers
from tools.team import TEAM_COMMON_TOOLS, bind_team_handlers
from tools.tool_handler import STANDARD_TOOLS_HANDLERS, STANDARD_TOOLS_LIST


TEAMMATE_READ_ONLY_TOOL_NAMES = {
    "read_file",
    "glob",
    "load_skill",
}
TEAMMATE_TASK_TOOL_NAMES = {
    "list_tasks",
    "get_task",
    "claim_task",
    "complete_task",
}


TEAMMATE_PROMPT = """
你是 Agent Team 中的一名 teammate。

你的名字：{name}
你的角色：{role}

规则：
1. 你的上下文独立于 team lead，并在 follow-up 之间保留。
2. 你只能对项目文件进行只读研究、分析和评审。
3. 使用共享 task 工具查看、认领并完成 lead 创建的任务。
4. 需要沟通时使用 send_message；peer 回复必须显式发送。
5. 不要创建 task、subagent 或 teammate，也不要修改任务依赖。
""".strip()


def _select_tool_definitions(names: set[str]) -> list[dict]:
    """从标准工具目录中选择指定名称的工具定义。"""

    return [
        tool
        for tool in STANDARD_TOOLS_LIST
        if tool.get("name") in names
    ]


def create_teammate_runtime(
    parent_runtime,
    coordinator,
    name: str,
    role: str,
):
    """创建一个项目文件只读的 teammate AgentRuntime。

    Args:
        parent_runtime: 当前 team lead Runtime。
        coordinator: 当前 session 的 TeamCoordinator。
        name: teammate 的稳定名称。
        role: teammate 职责说明。

    Returns:
        AgentRuntime: 与 lead 共享 session、但拥有独立 identity 和 history 的 Runtime。
    """

    model = dict(parent_runtime.policy.model)
    fallback_model = dict(parent_runtime.policy.fallback_model)
    read_only_handlers = {
        tool_name: STANDARD_TOOLS_HANDLERS[tool_name]
        for tool_name in TEAMMATE_READ_ONLY_TOOL_NAMES
    }
    task_handlers = {
        tool_name: handler
        for tool_name, handler in bind_task_handlers(coordinator.tasks).items()
        if tool_name in TEAMMATE_TASK_TOOL_NAMES
    }
    team_handlers = bind_team_handlers(
        coordinator,
        allow_lead_tools=False,
    )

    policy = RunPolicy(
        max_turns=50,
        prompt=TEAMMATE_PROMPT.format(
            name=name,
            role=role,
        ),
        model=model,
        fallback_model=fallback_model,
        tools_list=(
            _select_tool_definitions(
                TEAMMATE_READ_ONLY_TOOL_NAMES | TEAMMATE_TASK_TOOL_NAMES
            )
            + TEAM_COMMON_TOOLS
        ),
        tool_handler=(
            read_only_handlers
            | task_handlers
            | team_handlers
        ),
        can_ask_user=False,
    )
    teammate_state = state(
        messages=[],
        context={},
        max_output_tokens=parent_runtime.state.max_output_tokens,
        current_model=dict(model),
    )

    return RuntimeFactory.create(
        agent_name=name,
        policy=policy,
        state=teammate_state,
        memory_policy=MemoryPolicy(
            mode=MemoryMode.READ_ONLY,
            namespace="master",
        ),
        workspace=parent_runtime.paths.workspace,
        session_id=parent_runtime.session_id,
        events=parent_runtime.events,
        interaction=NonInteractiveInteraction(),
    )
