from threading import Thread
from time import sleep

import pytest

from team.bus import MessageBus
from team.contract import TeamMessage


def test_message_bus_preserves_order_and_isolates_mailboxes():
    bus = MessageBus()
    bus.register("alice")
    bus.register("bob")

    bus.send(TeamMessage(sender="lead", recipient="alice", content="one"))
    bus.send(TeamMessage(sender="lead", recipient="alice", content="two"))
    bus.send(TeamMessage(sender="lead", recipient="bob", content="other"))

    assert [message.content for message in bus.drain("alice")] == ["one", "two"]
    assert [message.content for message in bus.drain("bob")] == ["other"]


def test_message_bus_receive_waits_for_new_message():
    bus = MessageBus()
    bus.register("alice")

    def send_later():
        sleep(0.02)
        bus.send(TeamMessage(sender="lead", recipient="alice", content="ready"))

    thread = Thread(target=send_later)
    thread.start()
    message = bus.receive("alice", timeout=1)
    thread.join()

    assert message is not None
    assert message.content == "ready"


def test_message_bus_rejects_unknown_recipient():
    bus = MessageBus()

    with pytest.raises(KeyError, match="未知 team 收件人"):
        bus.send(TeamMessage(sender="lead", recipient="missing", content="hello"))
