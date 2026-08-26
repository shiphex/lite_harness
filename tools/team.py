"""LLM-facing Agent Teams 工具。

本模块只负责把模型工具调用适配为 ``TeamCoordinator`` API，并将协作结果
序列化为稳定文本。成员、任务、线程和消息状态均由 team 协作层管理。
"""

from dataclasses import asdict
import json

from team.coordinator import TeamCoordinator, TeamError
from tools.tool_class import ToolContext


TEAM_COMMON_TOOLS = [
    {
        "name": "send_message",
        "description": (
            "向 lead 或指定 teammate 发送一条单向中间 team 消息。"
            "每轮最终结果会由 Worker 自动且仅一次发送给 lead。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "recipient": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["recipient", "content"],
            "additionalProperties": False,
        },
    },
    {
        "name": "read_messages",
        "description": "非阻塞读取并清空发送给当前 Agent 的 team 消息。",
        "input_schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "list_team",
        "description": "查看当前 team、成员状态、任务归属和共享任务列表。",
        "input_schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
]
"""lead 和 teammate 都可以使用的协作工具定义。"""


TEAM_LEAD_TOOLS = [
    {
        "name": "spawn_teammate",
        "description": (
            "创建一个持久 teammate。researcher 与 lead 共享 workspace 且只能只读；"
            "writer 使用独立 Git worktree 并可以修改其中的文件。"
            "该操作必须经过用户审批。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_-]{0,31}$"},
                "role": {"type": "string"},
                "prompt": {"type": "string"},
                "profile": {
                    "type": "string",
                    "enum": ["researcher", "writer"],
                    "default": "researcher",
                },
            },
            "required": ["name", "role", "prompt"],
            "additionalProperties": False,
        },
    },
    {
        "name": "shutdown_teammate",
        "description": "请求指定 teammate 在当前 run 结束后协作式退出。",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        },
    },
]
"""仅 lead 可以使用的协作工具定义。"""


def _team_error_result(error: Exception) -> str:
    """将可预期协作异常转换为模型可处理的工具结果。"""

    return f"Team error: {error}"


def bind_team_handlers(
    coordinator: TeamCoordinator,
    *,
    allow_lead_tools: bool,
) -> dict:
    """将 team tools 绑定到指定 TeamCoordinator。

    Args:
        coordinator: 当前 master session 的 TeamCoordinator。
        allow_lead_tools: 是否加入 spawn 和 shutdown 等 lead-only handlers。

    Returns:
        dict: 可注入 ``RunPolicy.tool_handler`` 的 handler 映射。
    """

    def send_message(
        context: ToolContext,
        recipient: str,
        content: str,
    ) -> str:
        """发送一条单向 team 消息。"""

        try:
            message = coordinator.send(context.runtime, recipient, content)
        except (TeamError, KeyError) as error:
            return _team_error_result(error)
        return f"Message {message.message_id} sent to {recipient}"

    def read_messages(context: ToolContext) -> str:
        """读取当前 Agent 的全部未读 team 消息。"""

        try:
            messages = coordinator.read_messages(context.runtime)
        except (TeamError, KeyError) as error:
            return _team_error_result(error)
        return json.dumps(
            [asdict(message) for message in messages],
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    def list_team(context: ToolContext) -> str:
        """返回当前 team 快照。"""

        try:
            snapshot = coordinator.snapshot(context.runtime)
        except TeamError as error:
            return _team_error_result(error)
        return json.dumps(snapshot, ensure_ascii=False, indent=2, default=str)

    handlers = {
        "send_message": send_message,
        "read_messages": read_messages,
        "list_team": list_team,
    }

    if not allow_lead_tools:
        return handlers

    def spawn_teammate(
        context: ToolContext,
        name: str,
        role: str,
        prompt: str,
        profile: str = "researcher",
    ) -> str:
        """创建并启动一个持久 teammate。"""

        try:
            member = coordinator.spawn(
                parent_runtime=context.runtime,
                name=name,
                role=role,
                prompt=prompt,
                profile=profile,
            )
        except (TeamError, KeyError) as error:
            return _team_error_result(error)
        return json.dumps(asdict(member), ensure_ascii=False, indent=2, default=str)

    def shutdown_teammate(context: ToolContext, name: str) -> str:
        """请求一个 teammate 协作式停止。"""

        try:
            requested = coordinator.shutdown(context.runtime, name)
        except (TeamError, KeyError) as error:
            return _team_error_result(error)
        return (
            f"Shutdown requested: {name}"
            if requested
            else f"Teammate already stopped: {name}"
        )

    handlers.update({
        "spawn_teammate": spawn_teammate,
        "shutdown_teammate": shutdown_teammate,
    })
    return handlers
