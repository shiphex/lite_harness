from pathlib import Path
from types import SimpleNamespace

import builtin.load_prompt as load_prompt


def _runtime(tmp_path, tools=None, prompt=""):
    return SimpleNamespace(
        session_id="session",
        agent_id="agent",
        state=SimpleNamespace(turn_count=1),
        policy=SimpleNamespace(
            tools_list=tools or [],
            prompt=prompt,
        ),
        paths=SimpleNamespace(workspace=tmp_path),
    )


def test_list_skill_returns_empty_message(monkeypatch):
    monkeypatch.setattr(load_prompt, "SKILL_REGISTRY", {})

    assert "没有发现" in load_prompt.list_skill()


def test_list_skill_formats_registered_skills(monkeypatch):
    monkeypatch.setattr(
        load_prompt,
        "SKILL_REGISTRY",
        {
            "alpha": {"name": "alpha", "description": "Alpha skill"},
            "beta": {"name": "beta", "description": "Beta skill"},
        },
    )

    assert load_prompt.list_skill() == "- **alpha**: Alpha skill\n- **beta**: Beta skill"


def test_read_memory_index_returns_stripped_content(tmp_path):
    memory_index = tmp_path / "MEMORY.md"
    memory_index.write_text("\nPersistent project note\n", encoding="utf-8")

    assert load_prompt.read_memory_index(memory_index) == "Persistent project note"


def test_build_system_uses_workspace_and_memory_index(monkeypatch, tmp_path):
    memory_index = tmp_path / "MEMORY.md"
    memory_index.write_text("Project facts", encoding="utf-8")
    monkeypatch.setattr(load_prompt, "WORKDIR", tmp_path)
    monkeypatch.setattr(load_prompt, "MEMORY_INDEX", memory_index)
    monkeypatch.setattr(load_prompt, "list_skill", lambda: "- **demo**: Demo skill")

    system_prompt = load_prompt.build_system()

    assert str(tmp_path) in system_prompt
    assert "Demo skill" in system_prompt
    assert "Project facts" in system_prompt


def test_assemble_system_prompt_includes_policy_prompt_and_runtime_data(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        load_prompt,
        "PROMPT_SECTIONS",
        {
            "identity": "identity section",
            "skill": "skill section",
            "memory": "memory marker",
        },
    )
    runtime = _runtime(tmp_path, [{"name": "demo_tool"}], prompt="policy prompt")

    prompt = load_prompt.assemble_system_prompt(runtime, {"memories": "remember me"})

    assert prompt.split("\n\n")[:2] == ["policy prompt", "identity section"]
    assert "demo_tool" in prompt
    assert str(tmp_path) in prompt
    assert prompt.endswith("相关记忆：\nremember me")


def test_prompt_builder_caches_equivalent_context(monkeypatch, tmp_path):
    calls = []
    runtime = _runtime(tmp_path)

    monkeypatch.setattr(
        load_prompt,
        "assemble_system_prompt",
        lambda current_runtime, context: calls.append(context) or f"prompt {len(calls)}",
    )
    builder = load_prompt.PromptBuilder()

    assert builder.get_system_prompt(runtime, {"b": 2, "a": 1}) == "prompt 1"
    assert builder.get_system_prompt(runtime, {"a": 1, "b": 2}) == "prompt 1"
    assert len(calls) == 1


def test_prompt_builder_does_not_share_cache_between_instances(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        load_prompt,
        "assemble_system_prompt",
        lambda current_runtime, context: calls.append(current_runtime) or f"prompt {len(calls)}",
    )
    runtime = _runtime(tmp_path)

    first = load_prompt.PromptBuilder().get_system_prompt(runtime, {})
    second = load_prompt.PromptBuilder().get_system_prompt(runtime, {})

    assert first == "prompt 1"
    assert second == "prompt 2"


def test_prompt_builder_rebuilds_when_context_changes(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        load_prompt,
        "assemble_system_prompt",
        lambda current_runtime, context: calls.append(context) or f"prompt {len(calls)}",
    )
    builder = load_prompt.PromptBuilder()
    runtime = _runtime(tmp_path)

    assert builder.get_system_prompt(runtime, {"memories": ""}) == "prompt 1"
    assert builder.get_system_prompt(runtime, {"memories": "new"}) == "prompt 2"
    assert len(calls) == 2


def test_update_context_returns_tools_workspace_and_memories(monkeypatch, tmp_path):
    memory_index = tmp_path / "MEMORY.md"
    memory_index.write_text("Persistent project note", encoding="utf-8")
    monkeypatch.setattr(load_prompt, "WORKDIR", tmp_path)
    monkeypatch.setattr(load_prompt, "TOOLS_HANDLERS", {"shell": object()})

    assert load_prompt.update_context({}, [], memory_index=memory_index) == {
        "enabled_tools": ["shell"],
        "workspace": str(tmp_path),
        "memories": "Persistent project note",
    }
