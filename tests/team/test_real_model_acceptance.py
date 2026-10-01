"""Offline checks for the opt-in live TeamAgent acceptance entry point."""

import json
import re

from api.contract import ModelResponse, TextPart, ToolCallPart
from scripts.team_real_model_smoke import SmokeConfig
from scripts.team_real_model_acceptance import _LiveCase, run_acceptance


def _config():
    return SmokeConfig(
        api="openai",
        model_url="http://127.0.0.1:8000/v1",
        model_name="offline-test",
        api_key="no-key",
    )


class ScriptedAdapter:
    def __init__(self, mode="success"):
        self.mode = mode
        self.calls = {}

    def complete(self, request):
        prompt = next(
            json.loads(message["content"])
            for message in reversed(request.messages)
            if message["role"] == "user"
            and isinstance(message["content"], str)
            and message["content"].startswith("{")
        )
        task_id = prompt["task_id"]
        description = prompt["description"]
        names = {tool["name"] for tool in request.tools}
        if self.mode == "text" or "complete_team_task" not in names:
            return ModelResponse(content=[TextPart("waiting")], stop_reason="stop")
        if self.mode == "wrong_task":
            return self._call(task_id, "complete_team_task", {"task_id": "task_wrong"})
        if "send_team_message" in description and not self.calls.get((task_id, "send_team_message")):
            target = re.search(r'"target_id":"([^"]+)"', description).group(1)
            token = re.search(r'"content":"([^"]+)"', description).group(1)
            return self._call(task_id, "send_team_message", {"target_id": target, "content": token})
        if "receive_team_message" in description and not self.calls.get((task_id, "receive_team_message")):
            return self._call(task_id, "receive_team_message", {})
        if not self.calls.get((task_id, "complete_team_task")):
            return self._call(task_id, "complete_team_task", {"task_id": task_id})
        return ModelResponse(content=[TextPart("done")], stop_reason="stop")

    def _call(self, task_id, name, arguments):
        key = (task_id, name)
        self.calls[key] = self.calls.get(key, 0) + 1
        return ModelResponse(
            content=[ToolCallPart(f"call-{sum(self.calls.values())}", name, arguments)],
            stop_reason="tool_use",
        )


def test_three_scenarios_require_real_loop_tool_results(monkeypatch):
    adapter = ScriptedAdapter()
    monkeypatch.setattr("core.loop.create_adapter", lambda config: adapter)

    report = run_acceptance(_config())

    assert report["status"] == "passed"
    assert set(report["scenarios"]) == {"LIVE-01", "LIVE-02", "LIVE-03"}
    for scenario in report["scenarios"].values():
        assert scenario["status"] == "passed"
        assert scenario["model_responses"] > 0
        assert scenario["released"] is True
        assert scenario["category"] is None
        assert all(
            owner in scenario["member_states"]
            for owner in scenario["task_owners"].values()
        )
    assert report["scenarios"]["LIVE-01"]["message_verified"] is True
    assert report["scenarios"]["LIVE-02"]["resume_verified"] is True
    assert report["scenarios"]["LIVE-03"]["handoff_verified"] is True
    assert report["scenarios"]["LIVE-02"]["initial_teardown_failure_types"] == ["StopPendingTaskError"]
    assert report["scenarios"]["LIVE-03"]["initial_teardown_failure_types"] == ["StopPendingTaskError"]
    assert "no-key" not in json.dumps(report)


def test_text_only_model_cannot_pass_any_scenario(monkeypatch):
    adapter = ScriptedAdapter("text")
    monkeypatch.setattr("core.loop.create_adapter", lambda config: adapter)

    report = run_acceptance(_config())

    assert report["status"] == "failed"
    assert all(item["status"] == "failed" for item in report["scenarios"].values())
    assert all(item["category"] == "model_no_required_tool" for item in report["scenarios"].values())


def test_wrong_task_tool_and_failed_teardown_never_pass(monkeypatch):
    adapter = ScriptedAdapter("wrong_task")
    monkeypatch.setattr("core.loop.create_adapter", lambda config: adapter)
    wrong = run_acceptance(_config())
    assert wrong["status"] == "failed"
    assert all(item["status"] == "failed" for item in wrong["scenarios"].values())

    adapter = ScriptedAdapter()
    monkeypatch.setattr("core.loop.create_adapter", lambda config: adapter)
    from team.lifecycle import LifecycleManager

    monkeypatch.setattr(
        LifecycleManager,
        "teardown",
        lambda self: {"released": False, "failures": {"release": {"type": "InjectedError"}}},
    )
    blocked = run_acceptance(_config())
    assert blocked["status"] == "failed"
    assert all(item["status"] == "failed" for item in blocked["scenarios"].values())


def test_unexpected_scenario_error_still_attempts_final_release(monkeypatch):
    monkeypatch.setattr("core.loop.create_adapter", lambda config: ScriptedAdapter())

    def abort_before_assignment(self, task_id, agent_id):
        raise RuntimeError("controlled harness exception")

    monkeypatch.setattr(_LiveCase, "assigned", abort_before_assignment)

    report = run_acceptance(_config())

    assert report["status"] == "failed"
    assert all(item["category"] == "setup_or_runtime_error" for item in report["scenarios"].values())
    assert all(item["released"] is True for item in report["scenarios"].values())
