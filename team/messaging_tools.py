"""仅供 TeamAgent policy 使用的消息工具。"""

from dataclasses import asdict
import json
from typing import Callable

from tools.tool_class import ToolContext

from .agent import TeamAgent
from .contracts import MessageUnavailableError, TeamError


TEAM_AGENT_MESSAGE_TOOLS = [
    {
        "name": "send_team_message",
        "description": "给当前团队的一名 TeamAgent 发送文本消息。",
        "input_schema": {
            "type": "object",
            "properties": {
                "target_id": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["target_id", "content"],
            "additionalProperties": False,
        },
    },
    {
        "name": "receive_team_message",
        "description": "非阻塞读取当前 TeamAgent 的下一条团队消息。",
        "input_schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
]


def bind_message_handlers(
    get_agent: Callable[[str], TeamAgent],
) -> dict[str, Callable[..., str]]:
    """使用 ToolContext.runtime 定位当前 LifecycleManager 持有的 wrapper。"""

    def current_agent(context: ToolContext) -> TeamAgent:
        runtime = context.runtime
        agent_id = getattr(runtime, "agent_id", None)
        if not isinstance(agent_id, str):
            raise MessageUnavailableError("调用方没有有效的 TeamAgent identity")
        agent = get_agent(agent_id)
        if agent.runtime is not runtime:
            raise MessageUnavailableError("调用方 runtime 与 TeamAgent 不匹配")
        return agent

    def send_team_message(
        context: ToolContext, target_id: str, content: str
    ) -> str:
        try:
            current_agent(context).mailbox_handle.send(target_id, content)
        except TeamError as exc:
            return f"Team error [{type(exc).__name__}]: {exc}"
        return json.dumps({"status": "sent"}, ensure_ascii=False)

    def receive_team_message(context: ToolContext) -> str:
        try:
            message = current_agent(context).mailbox_handle.receive()
        except TeamError as exc:
            return f"Team error [{type(exc).__name__}]: {exc}"
        return json.dumps(
            {"message": asdict(message) if message is not None else None},
            ensure_ascii=False,
        )

    return {
        "send_team_message": send_team_message,
        "receive_team_message": receive_team_message,
    }
