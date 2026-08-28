"""Agent run 的通用控制契约。

工具可以通过这些不可变结果声明当前 run 应继续、重启或挂起。控制契约不理解
具体等待来源，Team、后台任务和外部审批等机制均可复用同一边界。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class RunDirective(StrEnum):
    """工具批次完成后，query loop 应执行的控制动作。"""

    CONTINUE = "continue"
    RESTART = "restart"
    SUSPEND = "suspend"


@dataclass(frozen=True, slots=True)
class SuspendRequest:
    """描述当前 run 的挂起原因以及恢复等待条件。"""

    kind: str
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolOutcome:
    """工具 handler 的标准返回值。"""

    content: str
    directive: RunDirective = RunDirective.CONTINUE
    suspend: SuspendRequest | None = None

    def __post_init__(self) -> None:
        if self.directive == RunDirective.SUSPEND and self.suspend is None:
            raise ValueError("SUSPEND ToolOutcome 必须提供 suspend request")


@dataclass(frozen=True, slots=True)
class ToolBatchResult:
    """一次 assistant tool batch 的完整执行结果和控制指令。"""

    results: list[dict]
    directive: RunDirective = RunDirective.CONTINUE
    suspend: SuspendRequest | None = None


def normalize_tool_outcome(value: Any) -> ToolOutcome:
    """将旧式 handler 返回值转换为标准 ToolOutcome。"""

    if isinstance(value, ToolOutcome):
        return value
    return ToolOutcome(content=str(value))
