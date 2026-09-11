"""Team-scoped MessageBus 的 Phase 1 composition shell。"""


class MessageBus:
    """拥有 mailbox storage；消息行为在后续 Messaging phase 实现。"""

    def __init__(self):
        self._mailboxes: dict[str, list[object]] = {}
