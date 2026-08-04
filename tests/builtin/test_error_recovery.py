import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from builtin import error_recovery


class RateLimitError(Exception):
    pass


class OverloadedError(Exception):
    pass


def test_retry_delay_uses_retry_after_when_present():
    assert error_recovery.retry_delay(2, retry_after=7) == 7


def test_retry_delay_uses_exponential_backoff_with_jitter(monkeypatch):
    monkeypatch.setattr(error_recovery.random, "uniform", lambda low, high: high)

    assert error_recovery.retry_delay(2) == 2.5


def test_with_retry_retries_rate_limit_errors(monkeypatch):
    calls = []
    state = error_recovery.RecoveryState()
    monkeypatch.setattr(error_recovery, "retry_delay", lambda attempt: 0)
    monkeypatch.setattr(error_recovery.time, "sleep", lambda delay: None)

    def flaky_call():
        calls.append("call")
        if len(calls) == 1:
            raise RateLimitError("429 too many requests")
        return "ok"

    assert error_recovery.with_retry(flaky_call, state) == "ok"
    assert calls == ["call", "call"]
    assert state.consecutive_529 == 0


def test_with_retry_switches_to_fallback_after_consecutive_overloads(monkeypatch):
    state = error_recovery.RecoveryState()
    state.current_model = "primary"
    monkeypatch.setattr(error_recovery, "MAX_RETRIES", 4)
    monkeypatch.setattr(error_recovery, "MAX_CONSECUTIVE_529", 3)
    monkeypatch.setattr(
        error_recovery,
        "model_config",
        {"model_name": "primary", "fallback_model_name": "fallback"},
    )
    monkeypatch.setattr(error_recovery, "retry_delay", lambda attempt: 0)
    monkeypatch.setattr(error_recovery.time, "sleep", lambda delay: None)

    calls = []

    def overloaded_then_success():
        calls.append("call")
        if len(calls) <= 3:
            raise OverloadedError("server overloaded")
        return "ok"

    assert error_recovery.with_retry(overloaded_then_success, state) == "ok"
    assert calls == ["call", "call", "call", "call"]
    assert state.current_model == "fallback"
    assert state.consecutive_529 == 0


def test_with_retry_reraises_non_transient_errors(monkeypatch):
    state = error_recovery.RecoveryState()
    monkeypatch.setattr(error_recovery.time, "sleep", lambda delay: None)

    with pytest.raises(ValueError, match="bad input"):
        error_recovery.with_retry(lambda: (_ for _ in ()).throw(ValueError("bad input")), state)


def test_with_retry_raises_when_retries_are_exhausted(monkeypatch):
    state = error_recovery.RecoveryState()
    monkeypatch.setattr(error_recovery, "MAX_RETRIES", 2)
    monkeypatch.setattr(error_recovery, "retry_delay", lambda attempt: 0)
    monkeypatch.setattr(error_recovery.time, "sleep", lambda delay: None)

    with pytest.raises(RuntimeError, match="Exceeded max retry attempts"):
        error_recovery.with_retry(lambda: (_ for _ in ()).throw(RateLimitError("429")), state)


def test_with_llm_retry_supports_mapping_state():
    state = {
        "consecutive_529": 0,
        "current_model": {"model_name": "primary"},
    }
    policy = {"fallback_model": {"model_name": "fallback", "API": "Anthropic"}}

    assert error_recovery.with_llm_retry(lambda: "ok", state, policy) == "ok"
    assert state["consecutive_529"] == 0
    assert state["current_model"] == {"model_name": "primary"}


def test_with_llm_retry_switches_mapping_state_to_fallback(monkeypatch):
    state = {
        "consecutive_529": 0,
        "current_model": {"model_name": "primary"},
    }
    policy = {
        "fallback_model": {
            "model_name": "fallback",
            "API": "OpenAI",
        }
    }
    calls = []

    monkeypatch.setattr(error_recovery, "MAX_RETRIES", 4)
    monkeypatch.setattr(error_recovery, "MAX_CONSECUTIVE_529", 2)
    monkeypatch.setattr(error_recovery, "retry_delay", lambda attempt: 0)
    monkeypatch.setattr(error_recovery.time, "sleep", lambda delay: None)

    def overloaded_then_success():
        calls.append("call")
        if len(calls) <= 2:
            raise OverloadedError("server overloaded")
        return "ok"

    assert error_recovery.with_llm_retry(overloaded_then_success, state, policy) == "ok"
    assert state["current_model"] == policy["fallback_model"]
    assert state["consecutive_529"] == 0


def test_output_tokens_recovery_supports_mapping_state():
    state = {
        "max_output_tokens_override": False,
        "recovery_count": 0,
    }
    messages = [{"role": "user", "content": "start"}]

    returned_state, returned_messages = error_recovery.output_tokens_too_long_error(
        messages,
        state,
    )

    assert returned_state is state
    assert returned_messages is messages
    assert state["max_output_tokens_override"] is True


@pytest.mark.parametrize(
    "message",
    [
        "prompt is too long",
        "context_length_exceeded",
        "max_context_window reached",
        "exceed_context_size: request exceeds the available context size",
        "The PROMPT became LONG after tool output",
    ],
)
def test_is_prompt_too_long_error_detects_known_markers(message):
    assert error_recovery.is_prompt_too_long_error(Exception(message)) is True


def test_is_prompt_too_long_error_returns_false_for_unrelated_errors():
    assert error_recovery.is_prompt_too_long_error(Exception("network unavailable")) is False


def test_max_tokens_too_long_error_escalates_before_appending_messages():
    state = error_recovery.RecoveryState()
    messages = [{"role": "user", "content": "start"}]

    returned_state, returned_messages = error_recovery.max_tokens_too_long_error(messages, state)

    assert returned_state is state
    assert returned_messages is messages
    assert state.has_escalated is True
    assert state.recovery_count == 0
    assert messages == [{"role": "user", "content": "start"}]


def test_max_tokens_too_long_error_appends_continuation_after_escalation():
    state = error_recovery.RecoveryState()
    state.has_escalated = True
    messages = [{"role": "user", "content": "start"}]

    error_recovery.max_tokens_too_long_error(messages, state)

    assert state.recovery_count == 1
    assert messages[-1] == {
        "role": "user",
        "content": error_recovery.CONTINUATION_PROMPT,
    }


def test_max_tokens_too_long_error_stops_after_recovery_limit(monkeypatch):
    state = error_recovery.RecoveryState()
    state.has_escalated = True
    state.recovery_count = 1
    messages = []
    monkeypatch.setattr(error_recovery, "MAX_RECOVERY_RETRIES", 1)

    error_recovery.max_tokens_too_long_error(messages, state)

    assert state.recovery_count == 1
    assert messages == []
