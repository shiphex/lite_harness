import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import core.loop as loop
from api.contract import ModelResponse, ToolCallPart


def _model_config(name):
    return {
        "API": "Anthropic",
        "model_name": name,
        "model_url": "http://localhost:8000",
        "api_key": "no-key",
    }


def _query_policy():
    return {
        "model": _model_config("primary"),
        "fallback_model": _model_config("fallback"),
        "context": {},
    }


def _query_state(model="primary"):
    if isinstance(model, str):
        model = _model_config(model)
    return {
        "messages": [{"role": "user", "content": "hello"}],
        "max_output_tokens": 128,
        "max_output_tokens_override": False,
        "recovery_count": 0,
        "has_attempted_reactive_compact": False,
        "current_model": model,
        "consecutive_529": 0,
    }


def _patch_query_loop_dependencies(monkeypatch, adapter):
    monkeypatch.setattr(loop, "compact_pipeline", lambda messages: (messages.copy(), messages))
    monkeypatch.setattr(loop, "struct_massages", lambda messages, memories: messages)
    monkeypatch.setattr(loop.builtin, "load_memories", lambda messages: "")
    monkeypatch.setattr(loop.builtin, "get_system_prompt", lambda context: "system")
    monkeypatch.setattr(loop.builtin, "extract_memories", lambda messages: None)
    monkeypatch.setattr(loop.builtin, "consolidate_memories", lambda: None)
    monkeypatch.setattr(loop.builtin, "with_llm_retry", lambda fn, state, policy: fn())
    monkeypatch.setattr(loop, "create_adapter", lambda config: adapter)
    monkeypatch.setattr(
        loop.hook,
        "trigger_hooks",
        lambda event, *args: "stop" if event == "Stop" else None,
    )
    monkeypatch.setattr(loop.tools, "TOOLS_LIST", [])

def test_agent_loop_compact_replaces_history_with_tool_result(monkeypatch):
    messages = [{"role": "user", "content": "please compact"}]
    context = {"memories": ""}
    calls = []
    compact_tool = SimpleNamespace(
        type="tool_use",
        name="compact",
        id="tool-compact",
        input={},
    )
    final_text = SimpleNamespace(type="text", text="done")

    responses = [
        SimpleNamespace(stop_reason="tool_use", content=[compact_tool]),
        SimpleNamespace(stop_reason="end_turn", content=[final_text]),
    ]

    def fake_call_model(**kwargs):
        calls.append(kwargs["messages"].copy())
        return responses.pop(0)

    monkeypatch.setattr(loop.api, "call_model", fake_call_model)
    monkeypatch.setattr(loop.tools, "tool_result_budget", lambda value: value)
    monkeypatch.setattr(loop.tools, "snip_compact", lambda value: value)
    monkeypatch.setattr(loop.tools, "micro_compact", lambda value: value)
    monkeypatch.setattr(loop.tools, "estimate_size", lambda value: 0)
    monkeypatch.setattr(loop.builtin, "load_memories", lambda messages: "")
    monkeypatch.setattr(loop.builtin, "get_system_prompt", lambda context: "system prompt")
    monkeypatch.setattr(loop.builtin, "update_context", lambda context, messages: context)
    monkeypatch.setattr(loop.builtin, "extract_memories", lambda messages: None)
    monkeypatch.setattr(loop.builtin, "consolidate_memories", lambda: None)
    monkeypatch.setattr(
        loop.tools,
        "compact_history",
        lambda value: [{"role": "user", "content": "[已压缩]\n\nsummary"}],
    )
    monkeypatch.setattr(loop.hook, "trigger_hooks", lambda *args: None)
    monkeypatch.setattr(loop.cli, "put_agent_other_info", lambda *args: None)

    loop.agent_loop(messages, context)

    assert messages == [
        {"role": "user", "content": "[已压缩]\n\nsummary"},
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tool-compact",
                    "content": "[已压缩： 对话历史已生成摘要。]",
                }
            ],
        },
        {"role": "assistant", "content": [final_text]},
    ]
    assert calls[1] == [
        {"role": "user", "content": "[已压缩]\n\nsummary"},
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tool-compact",
                    "content": "[已压缩： 对话历史已生成摘要。]",
                }
            ],
        },
    ]


def test_agent_loop_refreshes_context_after_tool_result(monkeypatch):
    messages = [{"role": "user", "content": "use a tool"}]
    context = {"memories": ""}
    system_prompts = []
    tool_block = SimpleNamespace(
        type="tool_use",
        name="demo_tool",
        id="tool-demo",
        input={"query": "hello"},
    )
    final_text = SimpleNamespace(type="text", text="done")

    responses = [
        SimpleNamespace(stop_reason="tool_use", content=[tool_block]),
        SimpleNamespace(stop_reason="end_turn", content=[final_text]),
    ]

    def fake_call_model(**kwargs):
        system_prompts.append(kwargs["system_prompt"])
        return responses.pop(0)

    def fake_get_system_prompt(value):
        return "refreshed system prompt" if value.get("refreshed") else "initial system prompt"

    def fake_update_context(value, current_messages):
        assert value is context
        assert current_messages[-1] == {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tool-demo",
                    "content": "tool output",
                }
            ],
        }
        return {"refreshed": True}

    monkeypatch.setattr(loop.api, "call_model", fake_call_model)
    monkeypatch.setattr(loop.tools, "TOOLS_LIST", [{"name": "demo_tool"}])
    monkeypatch.setattr(loop.tools, "tool_result_budget", lambda value: value)
    monkeypatch.setattr(loop.tools, "snip_compact", lambda value: value)
    monkeypatch.setattr(loop.tools, "micro_compact", lambda value: value)
    monkeypatch.setattr(loop.tools, "estimate_size", lambda value: 0)
    monkeypatch.setattr(loop.tools, "call_tool", lambda name, input: "tool output")
    monkeypatch.setattr(loop.builtin, "load_memories", lambda messages: "")
    monkeypatch.setattr(loop.builtin, "get_system_prompt", fake_get_system_prompt)
    monkeypatch.setattr(loop.builtin, "update_context", fake_update_context)
    monkeypatch.setattr(loop.builtin, "extract_memories", lambda messages: None)
    monkeypatch.setattr(loop.builtin, "consolidate_memories", lambda: None)
    monkeypatch.setattr(loop.hook, "trigger_hooks", lambda *args: None)
    monkeypatch.setattr(loop.cli, "put_agent_other_info", lambda *args: None)

    loop.agent_loop(messages, context)

    assert system_prompts == ["initial system prompt", "refreshed system prompt"]


def test_query_loop_uses_model_name_string_in_request(monkeypatch):
    requests = []

    class FakeAdapter:
        def complete(self, request):
            requests.append(request)
            return ModelResponse(stop_reason="end_turn", content=[])

    _patch_query_loop_dependencies(monkeypatch, FakeAdapter())

    state = _query_state(model="primary")
    result_state, status = loop.query_loop(_query_policy(), state)

    assert requests[0].model == "primary"
    assert result_state["messages"][-1]["role"] == "user"
    assert status == {"reason": "completed"}


def test_query_loop_stops_after_final_response_without_stop_hook_prompt(monkeypatch):
    requests = []

    class FakeAdapter:
        def complete(self, request):
            requests.append(request)
            return ModelResponse(stop_reason="end_turn", content=[])

    _patch_query_loop_dependencies(monkeypatch, FakeAdapter())
    monkeypatch.setattr(loop.hook, "trigger_hooks", lambda event, *args: None)

    state, status = loop.query_loop(_query_policy(), _query_state())

    assert len(requests) == 1
    assert status == {"reason": "completed"}
    assert state["messages"][-1]["role"] == "assistant"


def test_query_loop_reraises_non_prompt_error(monkeypatch):
    class FakeAdapter:
        def complete(self, request):
            raise ValueError("request failed")

    _patch_query_loop_dependencies(monkeypatch, FakeAdapter())
    monkeypatch.setattr(loop.builtin, "is_prompt_too_long_error", lambda error: False)

    with pytest.raises(ValueError, match="request failed"):
        loop.query_loop(_query_policy(), _query_state())


def test_query_loop_rebuilds_request_after_fallback_model_switch(monkeypatch):
    requests = []
    created_adapters = []

    class FakeAdapter:
        def complete(self, request):
            requests.append(request)
            return ModelResponse(stop_reason="end_turn", content=[])

    adapter = FakeAdapter()
    _patch_query_loop_dependencies(monkeypatch, adapter)
    policy = _query_policy()
    policy["fallback_model"]["API"] = "OpenAI"

    def fake_create_adapter(model_config):
        created_adapters.append(model_config.copy())
        return adapter

    monkeypatch.setattr(loop, "create_adapter", fake_create_adapter)

    def fake_retry(fn, state, policy):
        assert callable(fn)
        first_response = fn()
        state["current_model"] = dict(policy["fallback_model"])
        second_response = fn()
        assert first_response.stop_reason == "end_turn"
        return second_response

    monkeypatch.setattr(loop.builtin, "with_llm_retry", fake_retry)

    loop.query_loop(policy, _query_state())

    assert [request.model for request in requests] == ["primary", "fallback"]
    assert [(item["API"], item["model_name"]) for item in created_adapters] == [
        ("Anthropic", "primary"),
        ("OpenAI", "fallback"),
    ]


def test_query_loop_serializes_response_blocks_before_next_request(monkeypatch):
    requests = []
    responses = [
        ModelResponse(
            stop_reason="tool_use",
            content=[
                ToolCallPart(
                    id="tool-1",
                    name="demo_tool",
                    input={"value": 1},
                )
            ],
        ),
        ModelResponse(stop_reason="end_turn", content=[]),
    ]

    class FakeAdapter:
        def complete(self, request):
            requests.append(list(request.messages))
            return responses.pop(0)

    _patch_query_loop_dependencies(monkeypatch, FakeAdapter())
    monkeypatch.setattr(loop.tools, "call_tool", lambda name, input: "ok")

    loop.query_loop(_query_policy(), _query_state())

    assistant_message = requests[1][1]
    assert assistant_message == {
        "role": "assistant",
        "content": [
            {
                "type": "tool_use",
                "id": "tool-1",
                "name": "demo_tool",
                "input": {"value": 1},
            }
        ],
    }


def test_query_loop_reacts_to_prompt_too_long_error(monkeypatch):
    class PromptTooLongError(Exception):
        pass

    calls = []

    class FakeAdapter:
        def complete(self, request):
            calls.append(request)
            if len(calls) == 1:
                raise PromptTooLongError("context too long")
            return ModelResponse(stop_reason="end_turn", content=[])

    _patch_query_loop_dependencies(monkeypatch, FakeAdapter())
    monkeypatch.setattr(
        loop.builtin,
        "is_prompt_too_long_error",
        lambda error: isinstance(error, PromptTooLongError),
    )
    monkeypatch.setattr(loop.tools, "reactive_compact", lambda messages: messages)

    state = _query_state()
    result_state, status = loop.query_loop(_query_policy(), state)

    assert len(calls) == 2
    assert state["has_attempted_reactive_compact"] is True
    assert result_state is state
    assert status == {"reason": "completed"}
