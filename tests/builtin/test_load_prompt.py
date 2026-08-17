from pathlib import Path
from types import SimpleNamespace

import builtin.load_prompt as load_prompt


def _runtime(tmp_path, tools=None):
    return SimpleNamespace(
        policy=SimpleNamespace(tools_list=tools or []),
        paths=SimpleNamespace(workspace=tmp_path),
    )


def test_list_skill_returns_empty_message(monkeypatch):
    monkeypatch.setattr(load_prompt, "SKILL_REGISTRY", {})

    assert load_prompt.list_skill() == "(没有发现 skill。)"


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


def test_read_memory_index_returns_empty_string_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(load_prompt, "MEMORY_INDEX", tmp_path / "MEMORY.md")

    assert load_prompt.read_memory_index() == ""


def test_read_memory_index_strips_existing_file(tmp_path):
    memory_index = tmp_path / "MEMORY.md"
    memory_index.write_text("\n- [alpha](alpha.md) - Alpha memory\n\n", encoding="utf-8")

    assert load_prompt.read_memory_index(memory_index) == "- [alpha](alpha.md) - Alpha memory"


def test_build_system_uses_current_workspace_and_memory_index(monkeypatch, tmp_path):
    memory_index = tmp_path / "MEMORY.md"
    memory_index.write_text("- [project](project.md) - Project facts", encoding="utf-8")
    monkeypatch.setattr(load_prompt, "WORKDIR", tmp_path)
    monkeypatch.setattr(load_prompt, "MEMORY_INDEX", memory_index)
    monkeypatch.setattr(load_prompt, "list_skill", lambda: "- **demo**: Demo skill")

    system_prompt = load_prompt.build_system()

    assert str(tmp_path) in system_prompt
    assert "Demo skill" in system_prompt
    assert "Memories available:" in system_prompt
    assert "Project facts" in system_prompt


def test_assemble_system_prompt_uses_runtime_tools_and_workspace(monkeypatch, tmp_path):
    monkeypatch.setattr(
        load_prompt,
        "PROMPT_SECTIONS",
        {
            "identity": "identity section",
            "skill": "skill section",
            "memory": "memory marker",
        },
    )
    runtime = _runtime(tmp_path, [{"name": "demo_tool"}])

    assert load_prompt.assemble_system_prompt(runtime, {}) == (
        "identity section\n\n"
        "当前可用的 tool 有：demo_tool\n\n"
        f"当前工作目录是 {tmp_path}\n\n"
        "skill section\n\n"
        "memory marker"
    )


def test_assemble_system_prompt_appends_memories(monkeypatch, tmp_path):
    monkeypatch.setattr(
        load_prompt,
        "PROMPT_SECTIONS",
        {
            "identity": "identity section",
            "skill": "skill section",
            "memory": "memory marker",
        },
    )
    runtime = _runtime(tmp_path)

    prompt = load_prompt.assemble_system_prompt(runtime, {"memories": "remember me"})

    assert prompt.endswith("相关记忆：\nremember me")


def test_get_system_prompt_reuses_cache_for_equivalent_context(monkeypatch, tmp_path):
    calls = []
    runtime = _runtime(tmp_path)

    def fake_assemble(current_runtime, context):
        calls.append((current_runtime, context))
        return f"prompt {len(calls)}"

    monkeypatch.setattr(load_prompt, "_last_context_key", None)
    monkeypatch.setattr(load_prompt, "_last_prompt", None)
    monkeypatch.setattr(load_prompt, "assemble_system_prompt", fake_assemble)
    monkeypatch.setattr(load_prompt.cli, "put_agent_other_info", lambda *args: None)

    assert load_prompt.get_system_prompt(runtime, {"b": 2, "a": 1}) == "prompt 1"
    assert load_prompt.get_system_prompt(runtime, {"a": 1, "b": 2}) == "prompt 1"
    assert len(calls) == 1


def test_get_system_prompt_does_not_share_cache_between_runtimes(monkeypatch, tmp_path):
    monkeypatch.setattr(load_prompt, "_last_context_key", None)
    monkeypatch.setattr(load_prompt, "_last_prompt", None)
    monkeypatch.setattr(load_prompt.cli, "put_agent_other_info", lambda *args: None)
    runtime_a = _runtime(tmp_path / "a", [{"name": "a-tool"}])
    runtime_b = _runtime(tmp_path / "b", [{"name": "b-tool"}])

    first = load_prompt.get_system_prompt(runtime_a, {})
    second = load_prompt.get_system_prompt(runtime_b, {})

    assert "a-tool" in first
    assert "b-tool" in second


def test_get_system_prompt_rebuilds_when_context_changes(monkeypatch, tmp_path):
    calls = []
    runtime = _runtime(tmp_path)

    def fake_assemble(current_runtime, context):
        calls.append(context)
        return f"prompt {len(calls)}"

    monkeypatch.setattr(load_prompt, "_last_context_key", None)
    monkeypatch.setattr(load_prompt, "_last_prompt", None)
    monkeypatch.setattr(load_prompt, "assemble_system_prompt", fake_assemble)
    monkeypatch.setattr(load_prompt.cli, "put_agent_other_info", lambda *args: None)

    assert load_prompt.get_system_prompt(runtime, {"memories": ""}) == "prompt 1"
    assert load_prompt.get_system_prompt(runtime, {"memories": "new memory"}) == "prompt 2"
    assert len(calls) == 2


def test_update_context_returns_tools_workspace_and_memories(monkeypatch, tmp_path):
    memory_index = tmp_path / "MEMORY.md"
    memory_index.write_text("\nPersistent project note\n", encoding="utf-8")
    monkeypatch.setattr(load_prompt, "WORKDIR", tmp_path)
    monkeypatch.setattr(load_prompt, "TOOLS_HANDLERS", {"shell": object(), "todo_write": object()})

    assert load_prompt.update_context({}, [], memory_index=memory_index) == {
        "enabled_tools": ["shell", "todo_write"],
        "workspace": str(tmp_path),
        "memories": "Persistent project note",
    }


def test_update_context_uses_empty_memories_when_index_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(load_prompt, "WORKDIR", tmp_path)
    monkeypatch.setattr(load_prompt, "TOOLS_HANDLERS", {})

    assert load_prompt.update_context({}, [], memory_index=tmp_path / "missing.md") == {
        "enabled_tools": [],
        "workspace": str(tmp_path),
        "memories": "",
    }
