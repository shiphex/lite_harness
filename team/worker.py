"""持久 teammate Worker。

Worker 只负责把初始 prompt 和后续 mailbox 消息顺序交给 ``run_turn``，并将每轮
最终文本投递给 lead。模型调用、工具执行、Hook 和 history 仍由普通
``AgentRuntime + query_loop`` 负责，因此这里不形成第二套 Agent Loop。
"""

from collections.abc import Callable
from threading import Event as ThreadEvent
from threading import Thread

import event
from core.runner import run_turn
from core.runtime import AgentRuntime
from observability.logger import get_logger

from .bus import MessageBus
from .contract import MemberStatus, TeamMessage


logger = get_logger(__name__)


def extract_final_text(messages: list) -> str:
    """从 Runtime history 中提取最近的 Assistant 文本。

    Args:
        messages: Agent Runtime 的规范化消息列表。

    Returns:
        str: 最近一条包含文本的 Assistant 消息；不存在时返回空字符串。
    """

    for message in reversed(messages):
        if message.get("role") != "assistant":
            continue
        content = message.get("content", "")
        if isinstance(content, str):
            if content:
                return content
            continue
        if not isinstance(content, list):
            continue

        texts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(str(block.get("text", "")))
            elif getattr(block, "type", None) == "text":
                texts.append(str(getattr(block, "text", "")))
        result = "\n".join(text for text in texts if text)
        if result:
            return result
    return ""


class TeammateWorker:
    """在独立 daemon 线程中维护一个持久 teammate Runtime。"""

    def __init__(
        self,
        *,
        name: str,
        runtime: AgentRuntime,
        bus: MessageBus,
        on_status: Callable[[str, MemberStatus], None],
    ):
        """初始化 teammate Worker。

        Args:
            name: teammate 在 team 中的稳定名称。
            runtime: teammate 独立的 Agent Runtime。
            bus: team 共享 MessageBus。
            on_status: 成员状态变化回调。
        """

        self.name = name
        self.runtime = runtime
        self.bus = bus
        self.on_status = on_status
        self._stop = ThreadEvent()
        self._thread: Thread | None = None

    def start(self, initial_prompt: str) -> None:
        """启动 Worker，并将初始 prompt 作为 assignment 执行。

        Args:
            initial_prompt: lead 分配给 teammate 的首轮任务说明。

        Raises:
            RuntimeError: Worker 已经启动或底层线程无法启动时抛出。
        """

        if self._thread is not None:
            raise RuntimeError(f"teammate {self.name!r} 已经启动")

        assignment = TeamMessage(
            sender="lead",
            recipient=self.name,
            content=initial_prompt,
            kind="assignment",
        )
        self._thread = Thread(
            target=self._loop,
            args=(assignment,),
            name=f"team-{self.name}",
            daemon=True,
        )
        self._thread.start()

    def _loop(self, assignment: TeamMessage) -> None:
        """顺序处理 assignment 和后续 mailbox 消息。"""

        failed = False
        try:
            if not self._stop.is_set():
                self._emit_received(assignment)
                self._run_message(assignment)

            while not self._stop.is_set():
                message = self.bus.receive(self.name, timeout=0.5)
                if message is None:
                    continue
                if message.kind == "shutdown":
                    break
                self._emit_received(message)
                self._run_message(message)
        except Exception as error:
            failed = True
            logger.exception("teammate %s 执行失败", self.name)
            failure = TeamMessage(
                sender=self.name,
                recipient="lead",
                content=f"Teammate failed: {type(error).__name__}: {error}",
                kind="result",
            )
            try:
                self._send(failure)
            except Exception:
                logger.exception("teammate %s 失败结果投递失败", self.name)
            self.on_status(self.name, MemberStatus.FAILED)
        finally:
            if not failed:
                self.on_status(self.name, MemberStatus.STOPPED)

    def _run_message(self, message: TeamMessage) -> None:
        """把一条 team 消息转换为独立的 Agent run。"""

        self.on_status(self.name, MemberStatus.WORKING)
        prompt = (
            f'<team-message sender="{message.sender}" kind="{message.kind}">\n'
            f"{message.content}\n"
            "</team-message>"
        )
        state, status = run_turn(self.runtime, prompt)
        result = extract_final_text(state.messages)
        if not result:
            result = (
                f"teammate {self.name} 已结束本轮，但没有产生 Assistant 文本；"
                f"run status={status}"
            )

        # 隐式最终结果始终只发给 lead。peer 回复由模型显式调用 send_message，
        # 这样 peer 触发的 run 不会在两个 Worker 之间形成自动回复循环。
        self._send(TeamMessage(
            sender=self.name,
            recipient="lead",
            content=result,
            kind="result",
        ))
        self.on_status(self.name, MemberStatus.IDLE)

    def _send(self, message: TeamMessage) -> None:
        """投递 Worker 消息并记录发送事件。"""

        self.bus.send(message)
        self.runtime.events.emit(event.make_event(
            self.runtime,
            event.EventType.TEAM_MESSAGE_SENT,
            message_id=message.message_id,
            sender=message.sender,
            recipient=message.recipient,
            kind=message.kind,
        ))

    def _emit_received(self, message: TeamMessage) -> None:
        """记录 Worker 开始消费 mailbox 消息的事实。"""

        self.runtime.events.emit(event.make_event(
            self.runtime,
            event.EventType.TEAM_MESSAGE_RECEIVED,
            message_id=message.message_id,
            sender=message.sender,
            recipient=message.recipient,
            kind=message.kind,
        ))

    def stop(self) -> None:
        """请求 Worker 在当前 ``run_turn`` 完成后停止。

        停止标记负责阻止下一轮执行，shutdown 消息只用于唤醒正在 mailbox 上等待
        的线程。该流程不会强行中断模型调用。
        """

        self._stop.set()
        self.bus.send(TeamMessage(
            sender="system",
            recipient=self.name,
            content="shutdown",
            kind="shutdown",
        ))

    def join(self, timeout: float | None = None) -> None:
        """等待 Worker 线程退出。

        Args:
            timeout: 最长等待秒数；None 表示由线程库无限等待。
        """

        if self._thread is not None:
            self._thread.join(timeout)

    def is_alive(self) -> bool:
        """返回 Worker 线程是否仍在运行。

        Returns:
            bool: 线程已启动且尚未退出时返回 True。
        """

        return self._thread is not None and self._thread.is_alive()
