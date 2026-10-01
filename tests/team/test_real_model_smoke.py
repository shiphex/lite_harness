"""Offline checks for the explicitly invoked real-model smoke entry point."""

import json

import pytest

from api.contract import ModelResponse, TextPart, ToolCallPart
from scripts.team_real_model_smoke import SmokeConfig, parse_options, run_smoke


def _config():
    return SmokeConfig(
        api="openai",
        model_url="http://127.0.0.1:8000/v1",
        model_name="local-test",
        api_key="private-test-value",
    )


def test_real_loop_completes_one_task_with_bounded_requests(monkeypatch):
    requests = []

    class Adapter:
        def complete(self, request):
            requests.append(request)
            if len(requests) == 1:
                return ModelResponse(content=[], stop_reason="max_tokens")
            if len(requests) == 2:
                task_id = json.loads(request.messages[0]["content"])["task_id"]
                return ModelResponse(
                    content=[ToolCallPart("call-1", "complete_team_task", {"task_id": task_id})],
                    stop_reason="tool_use",
                )
            return ModelResponse(content=[TextPart("done")], stop_reason="stop")

    monkeypatch.setattr("core.loop.create_adapter", lambda config: Adapter())

    report = run_smoke(_config())

    assert report["status"] == "passed"
    assert report["model_responses"] == 3
    assert report["turns"] == 3
    assert report["completion_tool_called"] is True
    assert report["task_status"] == "completed"
    assert report["owner_matches"] is True
    assert report["member_state"] == "idle"
    assert report["released"] is True
    assert len(requests) == 3
    assert all(request.max_tokens <= 512 for request in requests)
    assert all(
        {tool["name"] for tool in request.tools} == {"get_team_task", "complete_team_task"}
        for request in requests
    )


def test_model_text_without_completion_is_a_failure(monkeypatch):
    class Adapter:
        def complete(self, request):
            return ModelResponse(content=[TextPart("I am done")], stop_reason="stop")

    monkeypatch.setattr("core.loop.create_adapter", lambda config: Adapter())

    report = run_smoke(_config())

    assert report["status"] == "failed"
    assert report["category"] == "model_no_completion_tool"
    assert report["model_responses"] == 1
    assert report["completion_tool_called"] is False
    assert report["task_status"] == "in_progress"
    assert report["owner_matches"] is True
    assert report["member_state"] == "busy"
    assert report["released"] is False
    assert report["teardown_failure_types"] == ["StopPendingTaskError"]


def test_cli_requires_explicit_auth_choice(monkeypatch):
    monkeypatch.delenv("SMOKE_API_KEY", raising=False)
    common = [
        "--api", "openai",
        "--model-url", "http://127.0.0.1:8000/v1",
        "--model-name", "local-test",
    ]
    with pytest.raises(SystemExit):
        parse_options(common)
    with pytest.raises(SystemExit):
        parse_options([*common, "--api-key-env", "SMOKE_API_KEY"])

    assert parse_options([*common, "--no-key"]).api_key == "no-key"


def test_cli_rejects_credentials_in_url(capsys):
    with pytest.raises(SystemExit):
        parse_options([
            "--api", "openai", "--model-url", "http://user:secret@localhost:8000/v1",
            "--model-name", "local-test", "--no-key",
        ])
    assert "secret" not in capsys.readouterr().err


def test_service_error_does_not_echo_credential(monkeypatch):
    class Adapter:
        def complete(self, request):
            raise ConnectionError("private-test-value")

    monkeypatch.setattr("core.loop.create_adapter", lambda config: Adapter())

    report = run_smoke(_config())

    assert report["status"] == "failed"
    assert report["category"] == "service_or_protocol_error"
    assert report["model_requests"] == 1
    assert report["model_responses"] == 0
    assert "private-test-value" not in json.dumps(report)


def test_runtime_error_is_not_mislabeled_as_service_failure(monkeypatch):
    class Adapter:
        def complete(self, request):
            raise RuntimeError("internal model handling error")

    monkeypatch.setattr("core.loop.create_adapter", lambda config: Adapter())

    report = run_smoke(_config())

    assert report["category"] == "execution_error"
