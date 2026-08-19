""" Event types """


from __future__ import annotations
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from core.runtime import AgentRuntime


class EventType(StrEnum):
    """ 事件类型定义 
    
    事件类型：
        - `run.started`：run 开始
        - `run.completed`：run 完成
        - `turn.started`：turn 开始
        - `assistant.message`：助手消息
        - `tool.requested`：工具请求
        - `tool.started`：工具开始
        - `tool.completed`：工具完成
        - `tool.blocked`：工具阻塞
        - `todo.updated`：待办事项更新
        - `compact.started`：压缩开始
        - `compact.completed`：压缩完成
        - `approval.requested`：审批请求
        - `approval.resolved`：审批解决
        - `error`：错误
    """
    # system
    SYSTEM_MESSAGE = "system.message"

    # run lifecycle
    RUN_STARTED = "run.started"
    RUN_COMPLETED = "run.completed"

    # query loop
    TURN_STARTED = "turn.started"

    # model
    ASSISTANT_MESSAGE = "assistant.message"

    # tool
    TOOL_REQUESTED = "tool.requested"
    TOOL_STARTED = "tool.started"
    TOOL_COMPLETED = "tool.completed"
    TOOL_BLOCKED = "tool.blocked"

    # todo
    TODO_UPDATED = "todo.updated"

    # compact
    COMPACT_STARTED = "compact.started"
    COMPACT_COMPLETED = "compact.completed"

    # interaction
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_RESOLVED = "approval.resolved"

    # error
    ERROR = "error"


@dataclass(slots=True, frozen=True)
class Event:
    """ 事件定义 
    
    Runtime 中已经发生的结构化事实。

    事件参数：
        - `type`：事件类型
        - `session_id`：会话 ID
        - `agent_id`：智能体 ID
        - `turn`：turn 号
        - `data`：事件数据
        - `timestamp`：事件时间戳
    """
    type: EventType

    session_id: str
    agent_id: str

    turn: int = 0

    data: dict[str, Any] = field(default_factory=dict)

    event_id: str = field(
        default_factory=lambda: uuid4().hex
    )

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


def make_event(
    runtime: AgentRuntime,
    event_type: EventType,
    **data: Any,
) -> Event:
    """根据 Runtime 上下文创建 Event。

    Args:
        runtime:
            当前 Agent Runtime。

        event_type:
            Event 类型。

        **data:
            当前事件特有的 payload。

    Returns:
        Event:
            已补充 Runtime 上下文的 Event。
    """

    return Event(
        type=event_type,
        session_id=runtime.session_id,
        agent_id=runtime.agent_id,
        turn=runtime.state.turn_count,
        data=data,
    )

