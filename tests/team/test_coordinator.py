from threading import Thread
from time import monotonic, sleep
from types import SimpleNamespace

import pytest

from event import EventType, MemoryEventSink, SynchronizedEventSink
from team.contract import MemberStatus, TeamMessage
from team.coordinator import TeamCoordinator, TeamError, TeamPermissionError
import team.worker as worker_module
from tools.task_system import claim_task, complete_task


def make_runtime(tmp_path, name, session_id, events):
    return SimpleNamespace(
        session_id=session_id,
        agent_id=f"{name}-id",
        agent_name=name,
        policy=SimpleNamespace(
            model={"model_name": "model"},
            fallback_model={"model_name": "fallback"},
        ),
        state=SimpleNamespace(
            messages=[],
            turn_count=0,
            max_output_tokens=100,
        ),
        paths=SimpleNamespace(workspace=tmp_path, state_root=tmp_path),
        events=events,
    )


def make_coordinator(
    tmp_path,
    monkeypatch,
    *,
    run_turn=None,
    max_members=3,
    bind_lead=True,
):
    memory_sink = MemoryEventSink()
    events = SynchronizedEventSink(memory_sink)
    lead = make_runtime(tmp_path, "lead", "session", events)

    def runtime_factory(
        parent,
        coordinator,
        name,
        role,
        *,
        profile,
        workspace,
    ):
        return make_runtime(tmp_path, name, parent.session_id, parent.events)

    coordinator = TeamCoordinator(
        team_id="team-session",
        workspace=tmp_path,
        runtime_factory=runtime_factory,
        max_members=max_members,
    )
    if bind_lead:
        coordinator.bind_lead(lead)

    if run_turn is None:
        def run_turn(runtime, prompt):
            runtime.state.messages.append({"role": "user", "content": prompt})
            runtime.state.messages.append({
                "role": "assistant",
                "content": [{"type": "text", "text": f"result:{runtime.agent_name}"}],
            })
            return runtime.state, {"reason": "completed"}

    monkeypatch.setattr(worker_module, "run_turn", run_turn)
    return coordinator, lead, memory_sink


def collect_messages(coordinator, lead, count, timeout=2):
    """在测试中收集指定数量的异步消息。"""

    messages = []
    deadline = monotonic() + timeout
    while len(messages) < count and monotonic() < deadline:
        messages.extend(coordinator.read_messages(lead))
        if len(messages) < count:
            sleep(0.01)
    return messages


def test_wait_for_results_collects_preexisting_results_for_all_members(
    tmp_path,
    monkeypatch,
):
    coordinator, lead, memory_sink = make_coordinator(tmp_path, monkeypatch)
    for name in ("alice", "bob"):
        coordinator.spawn(
            parent_runtime=lead,
            name=name,
            role="reviewer",
            prompt=f"review as {name}",
        )

    result = coordinator.wait_for_results(
        lead,
        ["alice", "bob"],
        timeout_seconds=2,
    )

    assert result.completed == ("alice", "bob")
    assert result.pending == ()
    assert result.timed_out is False
    assert {message.sender for message in result.messages} == {"alice", "bob"}
    received = [
        item
        for item in memory_sink.events
        if item.type == EventType.TEAM_MESSAGE_RECEIVED
        and item.data.get("kind") == "result"
    ]
    assert {item.data["sender"] for item in received} == {"alice", "bob"}
    coordinator.shutdown_all()


def test_wait_for_results_blocks_until_queue_notification(tmp_path, monkeypatch):
    coordinator, lead, _ = make_coordinator(tmp_path, monkeypatch)
    coordinator.spawn(
        parent_runtime=lead,
        name="alice",
        role="reviewer",
        prompt="initial work",
    )
    collect_messages(coordinator, lead, 1)

    def send_later():
        sleep(0.02)
        coordinator.bus.send(TeamMessage(
            sender="alice",
            recipient="lead",
            content="follow-up result",
            kind="result",
        ))

    thread = Thread(target=send_later)
    thread.start()
    result = coordinator.wait_for_results(
        lead,
        ["alice"],
        timeout_seconds=1,
    )
    thread.join()

    assert result.completed == ("alice",)
    assert [message.content for message in result.messages] == ["follow-up result"]
    coordinator.shutdown_all()


def test_wait_for_results_returns_other_messages_and_times_out(
    tmp_path,
    monkeypatch,
):
    coordinator, lead, _ = make_coordinator(tmp_path, monkeypatch)
    coordinator.spawn(
        parent_runtime=lead,
        name="alice",
        role="reviewer",
        prompt="initial work",
    )
    collect_messages(coordinator, lead, 1)
    coordinator.bus.send(TeamMessage(
        sender="alice",
        recipient="lead",
        content="progress",
        kind="message",
    ))

    result = coordinator.wait_for_results(
        lead,
        ["alice"],
        timeout_seconds=0.01,
    )

    assert result.completed == ()
    assert result.pending == ("alice",)
    assert result.timed_out is True
    assert [message.content for message in result.messages] == ["progress"]
    coordinator.shutdown_all()


def test_validate_wait_rejects_invalid_members_and_non_lead(tmp_path, monkeypatch):
    coordinator, lead, _ = make_coordinator(tmp_path, monkeypatch)

    with pytest.raises(TeamError, match="不能为空"):
        coordinator.validate_wait(lead, [])
    with pytest.raises(TeamError, match="未知 teammate"):
        coordinator.validate_wait(lead, ["missing"])

    coordinator.spawn(
        parent_runtime=lead,
        name="alice",
        role="reviewer",
        prompt="review",
    )
    teammate = coordinator.workers["alice"].runtime
    with pytest.raises(TeamPermissionError, match="只有 team lead"):
        coordinator.validate_wait(teammate, ["alice"])
    coordinator.shutdown_all()


def test_spawn_followup_persists_runtime_and_shutdown(tmp_path, monkeypatch):
    coordinator, lead, memory_sink = make_coordinator(tmp_path, monkeypatch)

    member = coordinator.spawn(
        parent_runtime=lead,
        name="alice",
        role="reviewer",
        prompt="review runtime",
    )
    first = collect_messages(coordinator, lead, 1)
    teammate_runtime = coordinator.workers["alice"].runtime

    assert member.current_task is None
    assert [item.content for item in first] == ["result:alice"]
    assert teammate_runtime.state.messages is not lead.state.messages
    assert teammate_runtime.session_id == lead.session_id
    assert teammate_runtime.agent_id != lead.agent_id

    coordinator.send(lead, "alice", "check one more detail")
    followup = collect_messages(coordinator, lead, 1)
    assert [item.content for item in followup] == ["result:alice"]
    assert len(teammate_runtime.state.messages) == 4

    assert coordinator.shutdown(lead, "alice") is True
    coordinator.workers["alice"].join(2)
    assert coordinator.members["alice"].status == MemberStatus.STOPPED

    event_types = [item.type for item in memory_sink.events]
    assert EventType.TEAM_MEMBER_SPAWNED in event_types
    assert EventType.TEAM_MESSAGE_SENT in event_types
    assert EventType.TEAM_MESSAGE_RECEIVED in event_types
    assert EventType.TEAM_MEMBER_STOPPED in event_types
    assert event_types.index(EventType.TEAM_MEMBER_SPAWNED) < event_types.index(
        EventType.TEAM_MEMBER_STATUS_CHANGED
    )


def test_current_task_is_derived_from_team_task_store(tmp_path, monkeypatch):
    coordinator, lead, _ = make_coordinator(tmp_path, monkeypatch)
    task = coordinator.tasks.create("review runtime", "")
    coordinator.spawn(
        parent_runtime=lead,
        name="alice",
        role="reviewer",
        prompt="review runtime",
    )
    collect_messages(coordinator, lead, 1)

    claim_task(task.id, owner="alice", store=coordinator.tasks)
    assert coordinator.list_members(lead)[0].current_task == task.id
    assert coordinator.snapshot(lead)["members"][0]["current_task"] == task.id

    complete_task(task.id, owner="alice", store=coordinator.tasks)
    assert coordinator.list_members(lead)[0].current_task is None
    coordinator.shutdown_all()


def test_team_task_store_limits_each_owner_to_one_active_task(tmp_path, monkeypatch):
    coordinator, _, _ = make_coordinator(tmp_path, monkeypatch)
    first = coordinator.tasks.create("first", "")
    second = coordinator.tasks.create("second", "")
    other_owner = coordinator.tasks.create("other owner", "")

    assert claim_task(first.id, owner="alice", store=coordinator.tasks).startswith(
        "Claimed"
    )
    denied = claim_task(second.id, owner="alice", store=coordinator.tasks)
    assert first.id in denied
    assert claim_task(
        other_owner.id,
        owner="bob",
        store=coordinator.tasks,
    ).startswith("Claimed")

    assert complete_task(first.id, owner="alice", store=coordinator.tasks).startswith(
        "Completed"
    )
    assert claim_task(second.id, owner="alice", store=coordinator.tasks).startswith(
        "Claimed"
    )


def test_worker_failure_marks_member_failed_and_reports_result(tmp_path, monkeypatch):
    def fail_run(runtime, prompt):
        raise RuntimeError("model failed")

    coordinator, lead, _ = make_coordinator(
        tmp_path,
        monkeypatch,
        run_turn=fail_run,
    )
    coordinator.spawn(
        parent_runtime=lead,
        name="alice",
        role="reviewer",
        prompt="fail",
    )
    result = collect_messages(coordinator, lead, 1)
    coordinator.workers["alice"].join(2)

    assert "Teammate failed" in result[0].content
    assert coordinator.members["alice"].status == MemberStatus.FAILED


def test_spawn_validates_name_capacity_and_name_reuse(tmp_path, monkeypatch):
    coordinator, lead, _ = make_coordinator(
        tmp_path,
        monkeypatch,
        max_members=1,
    )

    with pytest.raises(TeamError, match="name"):
        coordinator.spawn(
            parent_runtime=lead,
            name="invalid name",
            role="reviewer",
            prompt="review",
        )

    coordinator.spawn(
        parent_runtime=lead,
        name="alice",
        role="reviewer",
        prompt="review",
    )
    with pytest.raises(TeamError, match="上限"):
        coordinator.spawn(
            parent_runtime=lead,
            name="bob",
            role="reviewer",
            prompt="review",
        )

    coordinator.shutdown(lead, "alice")
    coordinator.workers["alice"].join(2)
    coordinator.spawn(
        parent_runtime=lead,
        name="bob",
        role="reviewer",
        prompt="review",
    )
    with pytest.raises(TeamError, match="已使用"):
        coordinator.spawn(
            parent_runtime=lead,
            name="alice",
            role="reviewer",
            prompt="review",
        )
    coordinator.shutdown_all()


def test_non_lead_cannot_spawn_or_shutdown(tmp_path, monkeypatch):
    coordinator, lead, _ = make_coordinator(tmp_path, monkeypatch)
    outsider = make_runtime(tmp_path, "outsider", "session", lead.events)

    with pytest.raises(TeamPermissionError):
        coordinator.spawn(
            parent_runtime=outsider,
            name="alice",
            role="reviewer",
            prompt="review",
        )

    coordinator.spawn(
        parent_runtime=lead,
        name="alice",
        role="reviewer",
        prompt="review",
    )
    with pytest.raises(TeamPermissionError):
        coordinator.shutdown(outsider, "alice")
    coordinator.shutdown_all()


def test_identity_binding_rejects_unbound_cross_session_and_fake_lead(tmp_path, monkeypatch):
    coordinator, lead, _ = make_coordinator(
        tmp_path,
        monkeypatch,
        bind_lead=False,
    )

    with pytest.raises(TeamPermissionError, match="尚未绑定"):
        coordinator.spawn(
            parent_runtime=lead,
            name="alice",
            role="reviewer",
            prompt="review",
        )

    coordinator.bind_lead(lead)
    with pytest.raises(TeamError, match="已绑定"):
        coordinator.bind_lead(lead)

    fake_lead = make_runtime(tmp_path, "fake", lead.session_id, lead.events)
    fake_lead.agent_name = "lead"
    with pytest.raises(TeamPermissionError):
        coordinator.spawn(
            parent_runtime=fake_lead,
            name="alice",
            role="reviewer",
            prompt="review",
        )

    cross_session = make_runtime(tmp_path, "lead", "other-session", lead.events)
    with pytest.raises(TeamPermissionError):
        coordinator.read_messages(cross_session)
    with pytest.raises(TeamPermissionError):
        coordinator.snapshot(fake_lead)

    coordinator.spawn(
        parent_runtime=lead,
        name="alice",
        role="reviewer",
        prompt="review",
    )
    with pytest.raises(TeamPermissionError):
        coordinator.shutdown(fake_lead, "alice")
    coordinator.shutdown_all()


def test_spawn_startup_failure_cleans_partial_member(tmp_path, monkeypatch):
    coordinator, lead, _ = make_coordinator(tmp_path, monkeypatch)

    def fail_factory(
        parent,
        current_coordinator,
        name,
        role,
        *,
        profile,
        workspace,
    ):
        raise RuntimeError("runtime factory failed")

    coordinator.runtime_factory = fail_factory
    with pytest.raises(RuntimeError, match="runtime factory failed"):
        coordinator.spawn(
            parent_runtime=lead,
            name="alice",
            role="reviewer",
            prompt="review",
        )

    assert "alice" not in coordinator.members
    with pytest.raises(KeyError):
        coordinator.bus.send(TeamMessage("lead", "alice", "hello"))


def test_runtime_factory_contract_is_not_silently_downgraded(
    tmp_path,
    monkeypatch,
):
    coordinator, lead, _ = make_coordinator(tmp_path, monkeypatch)

    def old_factory(parent, current_coordinator, name, role):
        return make_runtime(tmp_path, name, parent.session_id, parent.events)

    coordinator.runtime_factory = old_factory

    with pytest.raises(TypeError):
        coordinator.spawn(
            parent_runtime=lead,
            name="alice",
            role="reviewer",
            prompt="review",
        )

    assert "alice" not in coordinator.members


def test_teammate_runtime_state_root_must_be_lead_workspace(
    tmp_path,
    monkeypatch,
):
    coordinator, lead, _ = make_coordinator(tmp_path, monkeypatch)

    def wrong_state_root_factory(
        parent,
        current_coordinator,
        name,
        role,
        *,
        profile,
        workspace,
    ):
        runtime = make_runtime(tmp_path, name, parent.session_id, parent.events)
        runtime.paths.state_root = tmp_path / "wrong-state-root"
        return runtime

    coordinator.runtime_factory = wrong_state_root_factory

    with pytest.raises(TeamError, match="state_root"):
        coordinator.spawn(
            parent_runtime=lead,
            name="alice",
            role="reviewer",
            prompt="review",
        )

    assert "alice" not in coordinator.members


def test_worker_start_failure_keeps_failed_roster_and_event_order(tmp_path, monkeypatch):
    coordinator, lead, memory_sink = make_coordinator(tmp_path, monkeypatch)

    def fail_start(self, initial_prompt):
        raise RuntimeError("thread start failed")

    monkeypatch.setattr(worker_module.TeammateWorker, "start", fail_start)

    with pytest.raises(RuntimeError, match="thread start failed"):
        coordinator.spawn(
            parent_runtime=lead,
            name="alice",
            role="reviewer",
            prompt="review",
        )

    assert coordinator.members["alice"].status == MemberStatus.FAILED
    event_types = [item.type for item in memory_sink.events]
    assert event_types == [
        EventType.TEAM_MEMBER_SPAWNED,
        EventType.TEAM_MEMBER_STATUS_CHANGED,
    ]
    assert memory_sink.events[-1].data == {
        "member": "alice",
        "status": MemberStatus.FAILED,
    }


def test_peer_message_result_goes_to_lead_without_reply_loop(tmp_path, monkeypatch):
    coordinator, lead, _ = make_coordinator(tmp_path, monkeypatch)
    coordinator.spawn(
        parent_runtime=lead,
        name="alice",
        role="reviewer",
        prompt="alice work",
    )
    coordinator.spawn(
        parent_runtime=lead,
        name="bob",
        role="reviewer",
        prompt="bob work",
    )
    collect_messages(coordinator, lead, 2)

    alice_runtime = coordinator.workers["alice"].runtime
    coordinator.send(alice_runtime, "bob", "check this finding")
    result = collect_messages(coordinator, lead, 1)

    assert [item.sender for item in result] == ["bob"]
    assert [item.kind for item in result] == ["result"]
    assert coordinator.bus.drain("alice") == []
    coordinator.shutdown_all()


def test_messages_validate_recipient_and_use_runtime_metadata(tmp_path, monkeypatch):
    coordinator, lead, memory_sink = make_coordinator(tmp_path, monkeypatch)
    coordinator.spawn(
        parent_runtime=lead,
        name="alice",
        role="reviewer",
        prompt="review",
    )
    collect_messages(coordinator, lead, 1)
    alice_runtime = coordinator.workers["alice"].runtime

    with pytest.raises(TeamError, match="未知 teammate"):
        coordinator.send(alice_runtime, "missing", "hello")

    coordinator.send(alice_runtime, "lead", "explicit update")
    coordinator.read_messages(lead)
    sent = [
        item for item in memory_sink.events
        if item.type == EventType.TEAM_MESSAGE_SENT
        and item.data.get("sender") == "alice"
        and item.data.get("kind") == "message"
    ][-1]
    received = [
        item for item in memory_sink.events
        if item.type == EventType.TEAM_MESSAGE_RECEIVED
        and item.data.get("sender") == "alice"
        and item.data.get("kind") == "message"
    ][-1]
    assert sent.agent_id == alice_runtime.agent_id
    assert received.agent_id == lead.agent_id
    coordinator.shutdown_all()


def test_shutdown_all_reports_workers_still_running_after_timeout(tmp_path, monkeypatch):
    from threading import Event as ThreadEvent

    started = ThreadEvent()
    release = ThreadEvent()

    def blocking_run(runtime, prompt):
        started.set()
        release.wait(2)
        runtime.state.messages.append({
            "role": "assistant",
            "content": [{"type": "text", "text": "finished"}],
        })
        return runtime.state, {"reason": "completed"}

    coordinator, lead, memory_sink = make_coordinator(
        tmp_path,
        monkeypatch,
        run_turn=blocking_run,
    )
    coordinator.spawn(
        parent_runtime=lead,
        name="alice",
        role="reviewer",
        prompt="block",
    )
    assert started.wait(1)

    assert coordinator.shutdown_all(timeout_seconds=0.0) == ["alice"]
    timeout_event = memory_sink.events[-1]
    assert timeout_event.type == EventType.TEAM_MEMBER_SHUTDOWN_TIMEOUT
    assert timeout_event.agent_id == lead.agent_id
    assert timeout_event.data == {
        "members": ["alice"],
        "timeout_seconds": 0.0,
    }

    release.set()
    coordinator.workers["alice"].join(1)
    assert coordinator.shutdown_all(timeout_seconds=0.0) == []
