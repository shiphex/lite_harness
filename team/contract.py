"""Agent Teams 协作层的数据契约。

本模块仅定义 roster 和 mailbox 对外可见的数据结构，不持有 Runtime、工具或
线程对象。协作层可将这些结构直接序列化为工具结果和事件数据。
"""

from dataclasses import dataclass, field
from enum import StrEnum
from time import time
from uuid import uuid4


class MemberStatus(StrEnum):
    """teammate Worker 的生命周期状态。"""

    STARTING = "starting"
    WORKING = "working"
    IDLE = "idle"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class TeammateProfile(StrEnum):
    """teammate 的能力与 workspace 隔离级别。"""

    RESEARCHER = "researcher"
    WRITER = "writer"


@dataclass(slots=True, frozen=True)
class TeamMessage:
    """Agent Team 中传递的一条不可变消息。

    Args:
        sender: 发送者的 team name。
        recipient: 接收者的 team name。
        content: 消息正文。
        kind: 消息用途；MVP 使用 assignment、message、result 和 shutdown。
        message_id: 消息的唯一 ID。
        created_at: 消息创建时的 Unix 时间戳。
    """

    sender: str
    recipient: str
    content: str
    kind: str = "message"
    message_id: str = field(default_factory=lambda: uuid4().hex)
    created_at: float = field(default_factory=time)


@dataclass(slots=True)
class TeamMember:
    """协作平面中的 teammate 快照。

    ``current_task`` 是 Coordinator 生成快照时从 team-scoped TaskStore 推导出的
    只读视图，不在 Worker 生命周期中重复维护。

    Args:
        name: teammate 在 team 内的稳定名称。
        role: teammate 的职责说明。
        agent_id: teammate Runtime 的唯一 ID。
        status: 当前 Worker 生命周期状态。
        current_task: 当前认领且尚未完成的 task ID。
    """

    name: str
    role: str
    agent_id: str
    profile: TeammateProfile = TeammateProfile.RESEARCHER
    status: MemberStatus = MemberStatus.STARTING
    current_task: str | None = None
    workspace: str | None = None
    branch: str | None = None
