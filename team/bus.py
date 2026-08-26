"""Agent Teams 的进程内 mailbox。

MessageBus 为每个成员维护一条线程安全 FIFO 队列，只负责消息传输，不读取或
修改 Runtime history。首版 transport 仅存在于当前进程，session 关闭后不持久化。
"""

from queue import Empty, Queue
from threading import Lock

from .contract import TeamMessage


class MessageBus:
    """为单个 team 的成员维护相互隔离的线程安全 mailbox。"""

    def __init__(self):
        """初始化空的 mailbox 注册表。"""

        self._queues: dict[str, Queue[TeamMessage]] = {}
        self._lock = Lock()

    def register(self, name: str) -> None:
        """注册一个新 mailbox。

        Args:
            name: team 内唯一的成员名称。

        Raises:
            ValueError: 名称已注册时抛出。
        """

        with self._lock:
            if name in self._queues:
                raise ValueError(f"Mailbox {name!r} 已存在")
            self._queues[name] = Queue()

    def unregister(self, name: str) -> None:
        """注销 mailbox 并丢弃其中尚未读取的消息。

        Args:
            name: 需要注销的 mailbox；名称不存在时保持幂等。
        """

        with self._lock:
            self._queues.pop(name, None)

    def send(self, message: TeamMessage) -> None:
        """将消息放入接收者 mailbox。

        Args:
            message: 需要投递的 TeamMessage。

        Raises:
            KeyError: 接收者没有注册 mailbox 时抛出。
        """

        with self._lock:
            mailbox = self._queues.get(message.recipient)
        if mailbox is None:
            raise KeyError(f"未知 team 收件人: {message.recipient}")
        mailbox.put(message)

    def receive(
        self,
        name: str,
        timeout: float | None = None,
    ) -> TeamMessage | None:
        """等待并取出 mailbox 中最早的一条消息。

        Args:
            name: mailbox 名称。
            timeout: 最长等待秒数；None 表示无限等待。

        Returns:
            TeamMessage | None: 收到的消息；超时则返回 None。

        Raises:
            KeyError: mailbox 不存在时抛出。
        """

        with self._lock:
            mailbox = self._queues.get(name)
        if mailbox is None:
            raise KeyError(f"未知 mailbox: {name}")
        try:
            return mailbox.get(timeout=timeout)
        except Empty:
            return None

    def drain(self, name: str) -> list[TeamMessage]:
        """立即取出 mailbox 中的全部消息。

        Args:
            name: 需要读取的 mailbox 名称。

        Returns:
            list[TeamMessage]: 按入队顺序排列的未读消息。

        Raises:
            KeyError: mailbox 不存在时抛出。
        """

        with self._lock:
            mailbox = self._queues.get(name)
        if mailbox is None:
            raise KeyError(f"未知 mailbox: {name}")

        messages = []
        while True:
            try:
                messages.append(mailbox.get_nowait())
            except Empty:
                return messages
