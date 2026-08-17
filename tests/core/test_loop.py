from pathlib import Path
from types import SimpleNamespace

import pytest

import event
from api.contract import ModelResponse, TextPart, ToolCallPart
from builtin.artifacts import ArtifactStore
from builtin.memory import MemoryPolicy, MemoryMode
from core import loop
from core.runtime import AgentRuntime, RunPolicy, RuntimePaths, state
from event import EventType, MemoryEventSink
from event.interaction import ApprovalResponse
from hook.hook_handler import HookAction, HookEvent, HookManager, HookResult, create_default_hooks
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


class InteractionSpy:
    def __init__(self, approved=True, message=None):
        self.approved = approved
        self.message = message
        self.requests = []

    def request_approval(self, request):
        self.requests.append(request)
        return ApprovalResponse(
            approved=self.approved,
            message=self.message,
        )


def make_runtime(
    tmp_path,
    *,
    messages=None,
    max_turns=10,
    tools_list=None,
    tool_handler=None,
    hooks=None,
    events=None,
    interaction=None,
):
    tools_list = tools_list if tools_list is not None else []
    tool_handler = tool_handler or {"demo_tool": lambda value=None: f"demo:{value}"}
    policy = RunPolicy(
        max_turns=max_turns,
        model={"api": "fake", "model_name": "primary"},
        fallback_model={"api": "fake", "model_name": "fallback"},
        tools_list=tools_list,
        tool_handler=tool_handler,
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
        hooks=hooks if hooks is not None else HookManager(),
        events=events if events is not None else MemoryEventSink(),
        interaction=interaction if interaction is not None else InteractionSpy(),
    )


def patch_loop_dependencies(monkeypatch, runtime, adapter):
    monkeypatch.setattr(loop, "compact_pipeline", lambda value: (
        list(value.state.messages), value.state.messages
    ))
    monkeypatch.setattr(loop, "struct_massages", lambda messages, memories: list(messages))
    monkeypatch.setattr(loop.builtin, "with_llm_retry", lambda fn, state, policy: fn())
    monkeypatch.setattr(loop, "create_adapter", lambda model: adapter)
    monkeypatch.setattr(
        runtime.hooks,
        "run",
        lambda event, ctx, *args: HookResult(),
    )


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


def test_compact_pipeline_emits_start_and_complete_events(monkeypatch, tmp_path):
    runtime = make_runtime(tmp_path)
    monkeypatch.setattr(
        loop.tools,
        "tool_result_budget",
        lambda messages, artifacts: messages,
    )
    monkeypatch.setattr(loop.tools, "snip_compact", lambda messages: messages)
    monkeypatch.setattr(loop.tools, "micro_compact", lambda messages: messages)

    pre_compress, messages = loop.compact_pipeline(runtime)

    assert pre_compress == [{"role": "user", "content": "hello"}]
    assert messages == runtime.state.messages
    assert [item.type for item in runtime.events.events] == [
        EventType.COMPACT_STARTED,
        EventType.COMPACT_COMPLETED,
    ]
    assert runtime.events.events[0].data == {"trigger": "auto start compact."}
    assert runtime.events.events[1].data == {"trigger": "auto complete compact."}


def test_query_loop_emits_turn_and_run_lifecycle_events(monkeypatch, tmp_path):
    runtime = make_runtime(tmp_path)

    def compact_with_events(current_runtime):
        current_runtime.events.emit(
            event.make_event(
                current_runtime,
                EventType.COMPACT_STARTED,
                trigger="test compact start",
            )
        )
        current_runtime.events.emit(
            event.make_event(
                current_runtime,
                EventType.COMPACT_COMPLETED,
                trigger="test compact complete",
            )
        )
        return list(current_runtime.state.messages), current_runtime.state.messages

    monkeypatch.setattr(loop, "compact_pipeline", compact_with_events)
    monkeypatch.setattr(loop.builtin, "with_llm_retry", lambda fn, state, policy: fn())
    monkeypatch.setattr(
        loop,
        "create_adapter",
        lambda model: SimpleNamespace(
            complete=lambda request: ModelResponse(
                content=[TextPart("done")],
                stop_reason="end_turn",
            )
        ),
    )
    monkeypatch.setattr(
        runtime.hooks,
        "run",
        lambda event, ctx, *args: HookResult(),
    )

    loop.query_loop(runtime)

    assert [item.type for item in runtime.events.events] == [
        EventType.TURN_STARTED,
        EventType.COMPACT_STARTED,
        EventType.COMPACT_COMPLETED,
        EventType.RUN_COMPLETED,
    ]
    assert runtime.events.events[0].data == {"trigger": "turn 1 started"}
    assert runtime.events.events[-1].data == {"trigger": "run completed"}


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
    runtime = make_runtime(tmp_path, tools_list=[{"name": "demo_tool"}])
    runtime.tools.execute = lambda name, args: executed.append((name, args)) or "ok"
    block = ToolCallPart(id="blocked", name="demo_tool", input={})
    allowed = ToolCallPart(id="allowed", name="demo_tool", input={"value": 2})

    hook_events = []

    def run(event, ctx, *args):
        hook_events.append(event)
        if event == HookEvent.PRE_TOOL_USE and args[0] is block:
            return HookResult(
                action=HookAction.BLOCK,
                message="blocked by policy",
            )
        return HookResult()

    monkeypatch.setattr(runtime.hooks, "run", run)

    results, status = loop.execute_tool(
        ModelResponse(content=[block, allowed], stop_reason="tool_use"), runtime
    )

    assert status == "complete"
    assert executed == [("demo_tool", {"value": 2})]
    assert results == [
        {"type": "tool_result", "tool_use_id": "blocked", "content": "blocked by policy"},
        {"type": "tool_result", "tool_use_id": "allowed", "content": "ok"},
    ]
    assert hook_events == [
        HookEvent.PRE_TOOL_USE,
        HookEvent.PRE_TOOL_USE,
        HookEvent.POST_TOOL_USE,
    ]
    assert [event.type for event in runtime.events.events] == [
        EventType.TOOL_REQUESTED,
        EventType.COMPACT_STARTED,
        EventType.COMPACT_COMPLETED,
        EventType.TOOL_BLOCKED,
        EventType.TOOL_REQUESTED,
        EventType.COMPACT_STARTED,
        EventType.COMPACT_COMPLETED,
        EventType.TOOL_STARTED,
        EventType.TOOL_COMPLETED,
    ]


def test_execute_tool_denied_approval_does_not_execute_dangerous_command(tmp_path):
    executed = []
    interaction = InteractionSpy(approved=False, message="user cancelled")
    runtime = make_runtime(
        tmp_path,
        tools_list=[{"name": "powershell"}],
        tool_handler={
            "powershell": lambda command: executed.append(command) or "simulated",
        },
        hooks=create_default_hooks(),
        interaction=interaction,
    )
    block = ToolCallPart(
        id="remove-1",
        name="powershell",
        input={"command": "Remove-Item test.py"},
    )

    results, status = loop.execute_tool(
        ModelResponse(content=[block], stop_reason="tool_use"), runtime
    )

    assert status == "complete"
    assert executed == []
    assert len(interaction.requests) == 1
    assert interaction.requests[0].tool_call_id == "remove-1"
    assert interaction.requests[0].tool_name == "powershell"
    assert interaction.requests[0].arguments == {"command": "Remove-Item test.py"}
    assert results == [{
        "type": "tool_result",
        "tool_use_id": "remove-1",
        "content": "user cancelled",
    }]
    assert [event.type for event in runtime.events.events] == [
        EventType.TOOL_REQUESTED,
        EventType.COMPACT_STARTED,
        EventType.COMPACT_COMPLETED,
        EventType.APPROVAL_REQUESTED,
        EventType.APPROVAL_RESOLVED,
        EventType.TOOL_BLOCKED,
    ]
    assert runtime.events.events[3].data == {
        "tool_call_id": "remove-1",
        "tool_name": "powershell",
        "arguments": {"command": "Remove-Item test.py"},
        "reason": interaction.requests[0].reason,
    }
    assert runtime.events.events[4].data == {
        "tool_call_id": "remove-1",
        "tool_name": "powershell",
        "approved": False,
    }
    assert runtime.events.events[5].data == {
        "tool_call_id": "remove-1",
        "tool_name": "powershell",
        "reason": "user cancelled",
    }


def test_execute_tool_approved_dangerous_command_executes_once(tmp_path):
    executed = []
    interaction = InteractionSpy(approved=True)
    runtime = make_runtime(
        tmp_path,
        tools_list=[{"name": "powershell"}],
        tool_handler={
            "powershell": lambda command: executed.append(command) or "simulated",
        },
        hooks=create_default_hooks(),
        interaction=interaction,
    )
    block = ToolCallPart(
        id="remove-2",
        name="powershell",
        input={"command": "Remove-Item test.py"},
    )

    results, status = loop.execute_tool(
        ModelResponse(content=[block], stop_reason="tool_use"), runtime
    )

    assert status == "complete"
    assert executed == ["Remove-Item test.py"]
    assert interaction.requests[0].reason
    assert results == [{
        "type": "tool_result",
        "tool_use_id": "remove-2",
        "content": "simulated",
    }]
    assert [event.type for event in runtime.events.events] == [
        EventType.TOOL_REQUESTED,
        EventType.COMPACT_STARTED,
        EventType.COMPACT_COMPLETED,
        EventType.APPROVAL_REQUESTED,
        EventType.APPROVAL_RESOLVED,
        EventType.TOOL_STARTED,
        EventType.TOOL_COMPLETED,
    ]
    assert runtime.events.events[3].data["tool_call_id"] == "remove-2"
    assert runtime.events.events[4].data == {
        "tool_call_id": "remove-2",
        "tool_name": "powershell",
        "approved": True,
    }


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
    def run(event, ctx, *args):
        if event == HookEvent.STOP:
            return HookResult(action=HookAction.BLOCK, message="please continue")
        return HookResult()

    monkeypatch.setattr(runtime.hooks, "run", run)

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


def test_query_loop_emits_error_and_completion_when_prompt_stays_too_long(
    monkeypatch,
    tmp_path,
):
    class PromptTooLong(Exception):
        pass

    runtime = make_runtime(tmp_path)
    patch_loop_dependencies(
        monkeypatch,
        runtime,
        SimpleNamespace(
            complete=lambda request: (_ for _ in ()).throw(
                PromptTooLong("context is too long")
            ),
        ),
    )
    monkeypatch.setattr(
        loop.builtin,
        "is_prompt_too_long_error",
        lambda error: isinstance(error, PromptTooLong),
    )
    monkeypatch.setattr(
        loop.tools,
        "reactive_compact",
        lambda messages, artifacts: messages,
    )

    result_state, status = loop.query_loop(runtime)

    assert result_state is runtime.state
    assert status == {"reason": "prompt_too_long"}
    assert [item.type for item in runtime.events.events] == [
        EventType.TURN_STARTED,
        EventType.COMPACT_STARTED,
        EventType.TURN_STARTED,
        EventType.ERROR,
        EventType.RUN_COMPLETED,
    ]
    assert runtime.events.events[0].data == {
        "trigger": "turn 1 started",
    }
    assert runtime.events.events[1].data == {
        "trigger": "prompt_too_long",
    }
    assert runtime.events.events[2].data == {
        "trigger": "turn 2 started",
    }
    assert runtime.events.events[3].data == {
        "code": "prompt_too_long",
        "message": "上下文过大，压缩后依然无法继续。",
        "recoverable": False,
    }
    assert runtime.events.events[4].data == {
        "trigger": "prompt_too_long",
    }


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
