


from typing import Protocol
from .event import Event, EventType


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