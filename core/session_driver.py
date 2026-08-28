"""Agent session 的同步运行驱动器。

SessionDriver 位于推理循环之外，负责驱动 run 的挂起、事件等待和恢复。它不参与
模型推理，也不使用 EventSink 作为控制总线。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import event

from .control import SuspendRequest
from .runner import run_turn

if TYPE_CHECKING:
    from core.runtime import AgentRuntime
    from team.coordinator import TeamCoordinator


class SessionDriver:
    """驱动一个 Agent Runtime 的运行、挂起、等待和恢复生命周期。"""

    def __init__(
        self,
        *,
        runtime: "AgentRuntime",
        team: "TeamCoordinator",
    ):
        self.runtime = runtime
        self.team = team

    def submit(self, user_input: str):
        """提交外部输入，并持续驱动到本次请求离开挂起状态。"""

        state, status = run_turn(self.runtime, user_input)
        while status["reason"] == "suspended":
            request = status["request"]
            notification = self._wait(request)
            self.runtime.events.emit(
                event.make_event(
                    self.runtime,
                    event.EventType.RUN_RESUMED,
                    kind=request.kind,
                )
            )
            state, status = run_turn(self.runtime, notification)
        return state, status

    def _wait(self, request: SuspendRequest) -> str:
        """按挂起请求类型等待对应外部事件。"""

        if request.kind == "team.results":
            return self._wait_team_results(request)
        raise RuntimeError(f"Unsupported suspend request: {request.kind}")

    def _wait_team_results(self, request: SuspendRequest) -> str:
        """等待 teammate results 并构造给 lead 的结构化通知。"""

        result = self.team.wait_for_results(
            self.runtime,
            request.payload["members"],
            timeout_seconds=request.payload.get("timeout_seconds"),
        )
        payload = {
            "kind": "team.results",
            "completed": result.completed,
            "pending": result.pending,
            "timed_out": result.timed_out,
            "messages": [
                {
                    "sender": message.sender,
                    "kind": message.kind,
                    "content": message.content,
                    "message_id": message.message_id,
                }
                for message in result.messages
            ],
        }
        return (
            "<team-notification>\n"
            + json.dumps(payload, ensure_ascii=False, indent=2)
            + "\n</team-notification>"
        )
