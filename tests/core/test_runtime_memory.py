from types import SimpleNamespace

from api.contract import ModelResponse
from builtin.artifacts import ArtifactStore
from builtin.memory import MemoryManager, MemoryMode, MemoryPolicy
from core import loop
from core.runtime import AgentRuntime, RunPolicy, RuntimePaths, state


def test_query_loop_uses_runtime_memory_index_for_prompt_context(tmp_path, monkeypatch):
    paths = RuntimePaths.create(tmp_path, "session", "agent")
    memory = MemoryManager(
        tmp_path / ".agents" / "memory" / "runtime",
        MemoryPolicy(mode=MemoryMode.READ_WRITE, namespace="runtime"),
    )
    memory._write_memory_file(
        name="project",
        mem_type="project",
        desc="Project facts",
        body="Runtime memory body",
    )
    runtime = AgentRuntime(
        session_id="session",
        agent_name="agent",
        agent_id="agent",
        policy=RunPolicy(
            max_turns=1,
            model={"model_name": "model"},
            tools_list=[],
        ),
        state=state(
            messages=[{"role": "user", "content": "hello"}],
            current_model={"model_name": "model"},
        ),
        paths=paths,
        memory=memory,
        artifacts=ArtifactStore(paths.tool_result_dir, paths.transcript_dir),
    )
    captured = {}

    monkeypatch.setattr(runtime.memory, "load", lambda messages: "")
    monkeypatch.setattr(runtime.memory, "extract", lambda messages: False)
    monkeypatch.setattr(runtime.memory, "consolidate", lambda: False)
    monkeypatch.setattr(loop, "compact_pipeline", lambda value: (value.state.messages.copy(), value.state.messages))
    monkeypatch.setattr(loop, "struct_massages", lambda messages, memories: messages)
    def capture_prompt(context):
        captured["context"] = context
        return "system"

    monkeypatch.setattr(loop.builtin, "get_system_prompt", capture_prompt)
    monkeypatch.setattr(loop.builtin, "with_llm_retry", lambda fn, state, policy: fn())
    monkeypatch.setattr(loop, "create_adapter", lambda model: SimpleNamespace(
        complete=lambda request: ModelResponse(stop_reason="end_turn", content=[])
    ))
    monkeypatch.setattr(loop.hook, "trigger_hooks", lambda *args: None)

    loop.query_loop(runtime)

    assert captured["context"]["memories"] == (
        "- [project](project.md) - Project facts"
    )
