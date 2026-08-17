from builtin.artifacts import ArtifactStore
from builtin.load_prompt import PromptBuilder
from builtin.memory import MemoryMode, MemoryPolicy, write_memory_file
from core import loop
from core.runtime import AgentRuntime, RunPolicy, RuntimeFactory, RuntimePaths, state
from event import MemoryEventSink, NullEventSink
from event.interaction import NonInteractiveInteraction
from hook.hook_handler import HookManager
from cli.cli_interaction import CliInteraction
from cli.event_sink import CliEventSink
from tools.tool_handler import ToolExecutor


def _policy():
    return RunPolicy(
        max_turns=1,
        model={"api": "fake", "model_name": "model"},
        tools_list=[{"name": "demo_tool"}],
        tool_handler={"demo_tool": lambda: "ok"},
    )


def test_runtime_factory_wires_isolated_paths_and_components(tmp_path):
    runtime = RuntimeFactory.create(
        agent_name="agent",
        policy=_policy(),
        state=state(
            messages=[{"role": "user", "content": "hello"}],
            current_model={"api": "fake", "model_name": "model"},
        ),
        memory_policy=MemoryPolicy(
            mode=MemoryMode.READ_WRITE,
            namespace="runtime",
        ),
        workspace=tmp_path,
        session_id="session",
    )

    assert runtime.paths.workspace == tmp_path
    assert runtime.paths.session_dir == tmp_path / ".agents" / "runs" / "session"
    assert runtime.paths.agent_dir.is_dir()
    assert runtime.memory.root == tmp_path / ".agents" / ".memory" / "runtime"
    assert runtime.artifacts.tool_result_dir == runtime.paths.tool_result_dir
    assert runtime.artifacts.transcript_dir == runtime.paths.transcript_dir
    assert isinstance(runtime.prompt, PromptBuilder)
    assert isinstance(runtime.tools, ToolExecutor)
    assert runtime.tools.allowed_tools == {"demo_tool"}
    assert isinstance(runtime.hooks, HookManager)
    assert isinstance(runtime.events, NullEventSink)
    assert isinstance(runtime.interaction, NonInteractiveInteraction)


def test_runtime_factory_preserves_injected_runtime_components(tmp_path):
    hooks = HookManager()
    events = MemoryEventSink()
    interaction = NonInteractiveInteraction()

    runtime = RuntimeFactory.create(
        agent_name="agent",
        policy=_policy(),
        state=state(
            messages=[{"role": "user", "content": "hello"}],
            current_model={"api": "fake", "model_name": "model"},
        ),
        memory_policy=MemoryPolicy(
            mode=MemoryMode.READ_WRITE,
            namespace="runtime",
        ),
        workspace=tmp_path,
        session_id="session",
        hooks=hooks,
        events=events,
        interaction=interaction,
    )

    assert runtime.hooks is hooks
    assert runtime.events is events
    assert runtime.interaction is interaction


def test_prompt_builder_uses_runtime_memory_index_and_updates_context(tmp_path, monkeypatch):
    runtime = RuntimeFactory.create(
        agent_name="agent",
        policy=_policy(),
        state=state(
            messages=[{"role": "user", "content": "project"}],
            current_model={"api": "fake", "model_name": "model"},
        ),
        memory_policy=MemoryPolicy(
            mode=MemoryMode.READ_WRITE,
            namespace="runtime",
        ),
        workspace=tmp_path,
        session_id="session",
    )
    write_memory_file(
        runtime.memory,
        "project",
        "project",
        "Project facts",
        "Runtime memory body",
    )
    captured = {}

    def capture_prompt(current_runtime, context):
        captured["context"] = context
        return "system"

    monkeypatch.setattr("builtin.load_prompt.get_system_prompt", capture_prompt)

    prompt = runtime.prompt.build(runtime)

    assert prompt == "system"
    assert captured["context"]["memories"] == (
        "- [project](project.md) - Project facts"
    )
    assert runtime.state.context["memories"] == (
        "- [project](project.md) - Project facts"
    )
