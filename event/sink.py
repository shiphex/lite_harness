

from threading import RLock
from typing import Protocol
from .event import Event


class EventSink(Protocol):
    """Event 消费端统一接口。"""

    def emit(self, event: Event) -> None:
        ...


class NullEventSink:
    """什么都不做的 EventSink。"""

    def emit(self, event: Event) -> None:
        pass


class FanoutEventSink:
    """将一个 Event 广播到多个 Sink。

    将需要广播的 Sink 添加到列表中，在 emit 方法中遍历列表，将事件发送到每个 Sink。
    
    Args:
        sinks: 要广播的 Sink 列表。
    
    """

    def __init__(self, *sinks: EventSink):
        self._sinks = list(sinks)

    def emit(self, event: Event) -> None:
        for sink in self._sinks:
            sink.emit(event)


class MemoryEventSink:
    """用于测试和调试的内存 EventSink。"""

    def __init__(self):
        self.events: list[Event] = []

    def emit(self, event: Event) -> None:
        self.events.append(event)

    def clear(self) -> None:
        self.events.clear()


class SynchronizedEventSink:
    """使用可重入锁串行化底层 EventSink 的并发写入。

    Agent Teams 中 lead 与多个 teammate 共享同一个消费端。该 wrapper 只负责
    ``emit`` 的线程安全，不改变事件内容、顺序或底层 Sink 的渲染策略。
    """

    def __init__(self, sink: EventSink):
        """初始化线程安全 EventSink。

        Args:
            sink: 需要被串行保护的底层 EventSink。
        """

        self._sink = sink
        self._lock = RLock()

    def emit(self, event: Event) -> None:
        """在互斥区内转发一个 Event。"""

        with self._lock:
            self._sink.emit(event)
