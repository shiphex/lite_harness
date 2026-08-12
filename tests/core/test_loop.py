from pathlib import Path
from types import SimpleNamespace

import pytest

from api.contract import ModelResponse, TextPart, ToolCallPart
from builtin.artifacts import ArtifactStore
from builtin.memory import MemoryPolicy, MemoryMode
from core import loop
from core.runtime import AgentRuntime, RunPolicy, RuntimePaths, state
from tools.tool_handler import ToolExecutor


class MemorySpy:
    def __init__(self, tmp_path):
        self.index_path = tmp_path / "memory" / "MEMORY.md"
        self.calls = []

    def load(self, runtime, messages):
        self.calls.append(("load", runtime, list(messages)))
        return ""

    def extract(self, runtime, messages):
        self.calls.append(("extract", runtime, list(messages)))
        return True

    def consolidate(self, runtime):
        self.calls.append(("consolidate", runtime))
        return True


def make_runtime(tmp_path, *, messages=None, max_turns=10, tools_list=None):
    policy = RunPolicy(
        max_turns=max_turns,
        model={"api": "fake", "model_name": "primary"},
        fallback_model={"api": "fake", "model_name": "fallback"},
        tools_list=tools_list or [],
        tool_handler={"demo_tool": lambda value=None: f"demo:{value}"},
    )
    current_state = state(
        messages=messages or [{"role": "user", "content": "hello"}],
        current_model=dict(policy.model),
    )
    paths = RuntimePaths.create(tmp_path, "session", "agent")
    return AgentRuntime(
        session_id="session",
        agent_name="agent",
        agent_id="agent",
        policy=policy,
        state=current_state,
        paths=paths,
        prompt=SimpleNamespace(build=lambda runtime: "system"),
        memory=MemorySpy(tmp_path),
        artifacts=ArtifactStore(paths.tool_result_dir, paths.transcript_dir),
        tools=ToolExecutor(policy.tool_handler, policy.tools_list, tmp_path),
    )


def patch_loop_dependencies(monkeypatch, runtime, adapter):
    monkeypatch.setattr(loop, "compact_pipeline", lambda value: (
        list(value.state.messages), value.state.messages
    ))
    monkeypatch.setattr(loop, "struct_massages", lambda messages, memories: list(messages))
    monkeypatch.setattr(loop.builtin, "with_llm_retry", lambda fn, state, policy: fn())
    monkeypatch.setattr(loop, "create_adapter", lambda model: adapter)
    monkeypatch.setattr(loop.hook, "trigger_hooks", lambda event, *args: None)
    monkeypatch.setattr(loop.cli, "put_agent_other_info", lambda *args: None)


def test_query_loop_appends_canonical_final_response(monkeypatch, tmp_path):
    class Adapter:
        def complete(self, request):
            return ModelResponse(
                content=[TextPart("done")],
                stop_reason="end_turn",
            )

    runtime = make_runtime(tmp_path)
    patch_loop_dependencies(monkeypatch, runtime, Adapter())

    result_state, status = loop.query_loop(runtime)

    assert result_state is runtime.state
    assert status == {"reason": "completed"}
    assert runtime.state.messages[-1] == {
        "role": "assistant",
        "content": [{"type": "text", "text": "done"}],
    }
    assert [call[0] for call in runtime.memory.calls] == [
        "load", "extract", "consolidate"
    ]


def test_query_loop_round_trips_tool_result_and_response_blocks(monkeypatch, tmp_path):
    requests = []
    responses = iter([
        ModelResponse(
            content=[ToolCallPart(id="call-1", name="demo_tool", input={"value": 1})],
            stop_reason="tool_use",
        ),
        ModelResponse(content=[TextPart("finished")], stop_reason="end_turn"),
    ])

    class Adapter:
        def complete(self, request):
            requests.append(list(request.messages))
            return next(responses)

    runtime = make_runtime(tmp_path, tools_list=[{"name": "demo_tool"}])
    patch_loop_dependencies(monkeypatch, runtime, Adapter())

    loop.query_loop(runtime)

    assert requests[1] == [
        {"role": "user", "content": "hello"},
        {
            "role": "assistant",
            "content": [{
                "type": "tool_use",
                "id": "call-1",
                "name": "demo_tool",
                "input": {"value": 1},
            }],
        },
        {
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": "call-1",
                "content": "demo:1",
            }],
        },
    ]


def test_execute_tool_honors_hook_block_and_triggers_post_hook(monkeypatch, tmp_path):
    executed = []
    events = []
    runtime = make_runtime(tmp_path, tools_list=[{"name": "demo_tool"}])
    runtime.tools.execute = lambda name, args: executed.append((name, args)) or "ok"
    block = ToolCallPart(id="blocked", name="demo_tool", input={})
    allowed = ToolCallPart(id="allowed", name="demo_tool", input={"value": 2})

    def trigger(event, *args):
        events.append(event)
        return "blocked by policy" if event == "PreToolUse" and args[0] is block else None

    monkeypatch.setattr(loop.hook, "trigger_hooks", trigger)
    monkeypatch.setattr(loop.cli, "put_agent_other_info", lambda *args: None)

    results, status = loop.execute_tool(
        ModelResponse(content=[block, allowed], stop_reason="tool_use"), runtime
    )

    assert status == "complete"
    assert executed == [("demo_tool", {"value": 2})]
    assert results == [
        {"type": "tool_result", "tool_use_id": "blocked", "content": "blocked by policy"},
        {"type": "tool_result", "tool_use_id": "allowed", "content": "ok"},
    ]
    assert events == ["PreToolUse", "PreToolUse", "PostToolUse"]


def test_query_loop_compact_uses_runtime_artifacts(monkeypatch, tmp_path):
    responses = iter([
        ModelResponse(
            content=[ToolCallPart(id="compact-1", name="compact", input={})],
            stop_reason="tool_use",
        ),
        ModelResponse(content=[], stop_reason="end_turn"),
    ])
    compact_artifacts = []

    class Adapter:
        def complete(self, request):
            return next(responses)

    runtime = make_runtime(tmp_path, tools_list=[{"name": "compact"}])
    patch_loop_dependencies(monkeypatch, runtime, Adapter())
    monkeypatch.setattr(
        loop.tools,
        "compact_history",
        lambda messages, artifacts: compact_artifacts.append(artifacts) or messages,
    )

    loop.query_loop(runtime)

    assert compact_artifacts == [runtime.artifacts]


def test_query_loop_appends_stop_hook_prompt(monkeypatch, tmp_path):
    runtime = make_runtime(tmp_path)
    patch_loop_dependencies(monkeypatch, runtime, SimpleNamespace(
        complete=lambda request: ModelResponse(content=[], stop_reason="end_turn")
    ))
    monkeypatch.setattr(
        loop.hook,
        "trigger_hooks",
        lambda event, *args: "please continue" if event == "Stop" else None,
    )

    loop.query_loop(runtime)

    assert runtime.state.messages[-1] == {
        "role": "user",
        "content": "please continue",
    }


def test_query_loop_stops_at_max_turns_after_tool_round(monkeypatch, tmp_path):
    runtime = make_runtime(
        tmp_path,
        max_turns=1,
        tools_list=[{"name": "demo_tool"}],
    )
    patch_loop_dependencies(monkeypatch, runtime, SimpleNamespace(
        complete=lambda request: ModelResponse(
            content=[ToolCallPart(id="call-1", name="demo_tool", input={})],
            stop_reason="tool_use",
        )
    ))

    result_state, status = loop.query_loop(runtime)

    assert result_state is runtime.state
    assert result_state.turn_count == 1
    assert status == {"reason": "max_turns"}


def test_query_loop_reacts_to_prompt_too_long_once(monkeypatch, tmp_path):
    class PromptTooLong(Exception):
        pass

    calls = []
    compact_calls = []

    class Adapter:
        def complete(self, request):
            calls.append(request)
            if len(calls) == 1:
                raise PromptTooLong("context is too long")
            return ModelResponse(content=[], stop_reason="end_turn")

    runtime = make_runtime(tmp_path)
    patch_loop_dependencies(monkeypatch, runtime, Adapter())
    monkeypatch.setattr(
        loop.builtin,
        "is_prompt_too_long_error",
        lambda error: isinstance(error, PromptTooLong),
    )
    monkeypatch.setattr(
        loop.tools,
        "reactive_compact",
        lambda messages, artifacts: compact_calls.append(artifacts) or messages,
    )

    loop.query_loop(runtime)

    assert len(calls) == 2
    assert compact_calls == [runtime.artifacts]
    assert runtime.state.has_attempted_reactive_compact is True


def test_query_loop_uses_fallback_model_after_retry_switch(monkeypatch, tmp_path):
    requests = []

    class Adapter:
        def complete(self, request):
            requests.append(request)
            return ModelResponse(content=[], stop_reason="end_turn")

    runtime = make_runtime(tmp_path)
    patch_loop_dependencies(monkeypatch, runtime, Adapter())

    def retry(fn, current_state, policy):
        first = fn()
        current_state.current_model = dict(policy.fallback_model)
        second = fn()
        assert first.stop_reason == "end_turn"
        return second

    monkeypatch.setattr(loop.builtin, "with_llm_retry", retry)

    loop.query_loop(runtime)

    assert [request.model for request in requests] == ["primary", "fallback"]
    assert runtime.state.current_model == runtime.policy.fallback_model


def test_query_loop_uses_current_output_budget_after_max_tokens(monkeypatch, tmp_path):
    requests = []
    responses = iter([
        ModelResponse(content=[], stop_reason="max_tokens"),
        ModelResponse(content=[], stop_reason="end_turn"),
    ])

    class Adapter:
        def complete(self, request):
            requests.append(request)
            return next(responses)

    runtime = make_runtime(tmp_path)
    runtime.state.max_output_tokens = 10
    runtime.state.recovery_count = 0
    patch_loop_dependencies(monkeypatch, runtime, Adapter())

    loop.query_loop(runtime)

    assert [request.max_tokens for request in requests] == [10, 20]
    assert runtime.state.max_output_tokens_override is True


def test_query_loop_reraises_non_prompt_errors(monkeypatch, tmp_path):
    runtime = make_runtime(tmp_path)
    patch_loop_dependencies(monkeypatch, runtime, SimpleNamespace(
        complete=lambda request: (_ for _ in ()).throw(ValueError("request failed"))
    ))
    monkeypatch.setattr(loop.builtin, "is_prompt_too_long_error", lambda error: False)

    with pytest.raises(ValueError, match="request failed"):
        loop.query_loop(runtime)
