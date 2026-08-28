import json
from types import SimpleNamespace

import pytest

from core.control import SuspendRequest
from core.session_driver import SessionDriver
from event import EventType, MemoryEventSink
from team.contract import TeamMessage, TeamWaitResult
import core.session_driver as driver_module


def make_runtime():
    return SimpleNamespace(
        session_id="session",
        agent_id="lead-id",
        state=SimpleNamespace(turn_count=1, messages=[]),
        events=MemoryEventSink(),
    )


def parse_notification(value: str) -> dict:
    prefix = "<team-notification>\n"
    suffix = "\n</team-notification>"
    assert value.startswith(prefix)
    assert value.endswith(suffix)
    return json.loads(value[len(prefix):-len(suffix)])


def test_session_driver_waits_and_resumes_with_team_notification(monkeypatch):
    runtime = make_runtime()
    request = SuspendRequest(
        kind="team.results",
        payload={"members": ["alice"], "timeout_seconds": 10},
    )
    message = TeamMessage(
        sender="alice",
        recipient="lead",
        content="review complete",
        kind="result",
    )
    wait_calls = []
    team = SimpleNamespace(
        wait_for_results=lambda current_runtime, members, timeout_seconds: (
            wait_calls.append((current_runtime, members, timeout_seconds))
            or TeamWaitResult(
                messages=(message,),
                completed=("alice",),
                pending=(),
            )
        )
    )
    run_calls = []

    def fake_run_turn(current_runtime, user_input):
        run_calls.append((current_runtime, user_input))
        if len(run_calls) == 1:
            return current_runtime.state, {
                "reason": "suspended",
                "request": request,
            }
        return current_runtime.state, {"reason": "completed"}

    monkeypatch.setattr(driver_module, "run_turn", fake_run_turn)

    state, status = SessionDriver(runtime=runtime, team=team).submit("start")

    assert state is runtime.state
    assert status == {"reason": "completed"}
    assert wait_calls == [(runtime, ["alice"], 10)]
    notification = parse_notification(run_calls[1][1])
    assert notification == {
        "kind": "team.results",
        "completed": ["alice"],
        "pending": [],
        "timed_out": False,
        "messages": [{
            "sender": "alice",
            "kind": "result",
            "content": "review complete",
            "message_id": message.message_id,
        }],
    }
    resumed = [item for item in runtime.events.events if item.type == EventType.RUN_RESUMED]
    assert len(resumed) == 1
    assert resumed[0].data == {"kind": "team.results"}


def test_session_driver_supports_timeout_then_another_suspend(monkeypatch):
    runtime = make_runtime()
    request = SuspendRequest(
        kind="team.results",
        payload={"members": ["alice"], "timeout_seconds": 1},
    )
    wait_results = iter([
        TeamWaitResult(messages=(), completed=(), pending=("alice",)),
        TeamWaitResult(messages=(), completed=("alice",), pending=()),
    ])
    team = SimpleNamespace(
        wait_for_results=lambda *args, **kwargs: next(wait_results)
    )
    run_inputs = []

    def fake_run_turn(current_runtime, user_input):
        run_inputs.append(user_input)
        if len(run_inputs) < 3:
            return current_runtime.state, {
                "reason": "suspended",
                "request": request,
            }
        return current_runtime.state, {"reason": "completed"}

    monkeypatch.setattr(driver_module, "run_turn", fake_run_turn)

    _, status = SessionDriver(runtime=runtime, team=team).submit("start")

    assert status == {"reason": "completed"}
    assert parse_notification(run_inputs[1])["timed_out"] is True
    assert parse_notification(run_inputs[2])["timed_out"] is False
    assert sum(
        item.type == EventType.RUN_RESUMED
        for item in runtime.events.events
    ) == 2


def test_session_driver_rejects_unknown_suspend_kind(monkeypatch):
    runtime = make_runtime()
    request = SuspendRequest(kind="unknown.event", payload={})
    monkeypatch.setattr(
        driver_module,
        "run_turn",
        lambda current_runtime, user_input: (
            current_runtime.state,
            {"reason": "suspended", "request": request},
        ),
    )

    with pytest.raises(RuntimeError, match="Unsupported suspend request"):
        SessionDriver(runtime=runtime, team=object()).submit("start")

    assert runtime.events.events == []
