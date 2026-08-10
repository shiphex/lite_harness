import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_module_from_path(module_name: str, relative_path: str):
    module_path = PROJECT_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


load_prompt = _load_module_from_path("load_prompt_under_test", "builtin/load_prompt.py")


def test_list_skill_returns_empty_message(monkeypatch):
    monkeypatch.setattr(load_prompt, "SKILL_REGISTRY", {}, raising=False)

    assert load_prompt.list_skill() == "(没有发现 skill。)"


def test_list_skill_formats_registered_skills(monkeypatch):
    monkeypatch.setattr(
        load_prompt,
        "SKILL_REGISTRY",
        {
            "alpha": {
                "name": "alpha",
                "description": "Alpha skill",
            },
            "beta": {
                "name": "beta",
                "description": "Beta skill",
            },
        },
        raising=False,
    )

    assert load_prompt.list_skill() == "- **alpha**: Alpha skill\n- **beta**: Beta skill"


def test_read_memory_index_returns_empty_string_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(load_prompt, "MEMORY_INDEX", tmp_path / "MEMORY.md", raising=False)

    assert load_prompt.read_memory_index() == ""


def test_read_memory_index_strips_existing_file(monkeypatch, tmp_path):
    memory_index = tmp_path / "MEMORY.md"
    memory_index.write_text("\n- [alpha](alpha.md) - Alpha memory\n\n", encoding="utf-8")
    monkeypatch.setattr(load_prompt, "MEMORY_INDEX", memory_index, raising=False)

    assert load_prompt.read_memory_index() == "- [alpha](alpha.md) - Alpha memory"


def test_build_system_without_memory_index(monkeypatch, tmp_path):
    monkeypatch.setattr(load_prompt, "WORKDIR", tmp_path, raising=False)
    monkeypatch.setattr(load_prompt, "MEMORY_INDEX", tmp_path / "missing.md", raising=False)
    monkeypatch.setattr(load_prompt, "list_skill", lambda: "- **demo**: Demo skill")

    system_prompt = load_prompt.build_system()

    assert f"位于 {tmp_path}" in system_prompt
    assert "当前系统环境是 Windows" in system_prompt
    assert "当前可用的 skill 有：- **demo**: Demo skill" in system_prompt
    assert "Memories available:" not in system_prompt


def test_build_system_includes_memory_index(monkeypatch, tmp_path):
    memory_index = tmp_path / "MEMORY.md"
    memory_index.write_text("- [project](project.md) - Project facts", encoding="utf-8")
    monkeypatch.setattr(load_prompt, "WORKDIR", tmp_path, raising=False)
    monkeypatch.setattr(load_prompt, "MEMORY_INDEX", memory_index, raising=False)
    monkeypatch.setattr(load_prompt, "list_skill", lambda: "(没有发现 skill。)")

    system_prompt = load_prompt.build_system()

    assert "当前可用的 skill 有：(没有发现 skill。)" in system_prompt
    assert "Memories available:\n- [project](project.md) - Project facts" in system_prompt


def test_assemble_system_prompt_uses_base_sections(monkeypatch):
    monkeypatch.setattr(
        load_prompt,
        "PROMPT_SECTIONS",
        {
            "identity": "identity section",
            "tools": "tools section",
            "workspace": "workspace section",
            "memory": "memory marker",
        },
        raising=False,
    )

    assert load_prompt.assemble_system_prompt({}) == (
        "identity section\n\n"
        "tools section\n\n"
        "workspace section"
    )


def test_assemble_system_prompt_appends_memories(monkeypatch):
    monkeypatch.setattr(
        load_prompt,
        "PROMPT_SECTIONS",
        {
            "identity": "identity section",
            "tools": "tools section",
            "workspace": "workspace section",
            "memory": "memory marker",
        },
        raising=False,
    )

    system_prompt = load_prompt.assemble_system_prompt({"memories": "remember me"})

    assert system_prompt == (
        "identity section\n\n"
        "tools section\n\n"
        "workspace section\n\n"
        "相关记忆：\nremember me"
    )


def test_get_system_prompt_reuses_cache_for_equivalent_context(monkeypatch):
    calls = []

    def fake_assemble(context):
        calls.append(context)
        return f"prompt {len(calls)}"

    monkeypatch.setattr(load_prompt, "_last_context_key", None, raising=False)
    monkeypatch.setattr(load_prompt, "_last_prompt", None, raising=False)
    monkeypatch.setattr(load_prompt, "assemble_system_prompt", fake_assemble)

    first_prompt = load_prompt.get_system_prompt({"b": 2, "a": 1})
    second_prompt = load_prompt.get_system_prompt({"a": 1, "b": 2})

    assert first_prompt == "prompt 1"
    assert second_prompt == "prompt 1"
    assert len(calls) == 1


def test_get_system_prompt_rebuilds_when_context_changes(monkeypatch):
    calls = []

    def fake_assemble(context):
        calls.append(context)
        return f"prompt {len(calls)}"

    monkeypatch.setattr(load_prompt, "_last_context_key", None, raising=False)
    monkeypatch.setattr(load_prompt, "_last_prompt", None, raising=False)
    monkeypatch.setattr(load_prompt, "assemble_system_prompt", fake_assemble)

    first_prompt = load_prompt.get_system_prompt({"memories": ""})
    second_prompt = load_prompt.get_system_prompt({"memories": "new memory"})

    assert first_prompt == "prompt 1"
    assert second_prompt == "prompt 2"
    assert len(calls) == 2


def test_update_context_returns_tools_workspace_and_memories(monkeypatch, tmp_path):
    memory_index = tmp_path / "MEMORY.md"
    memory_index.write_text("\nPersistent project note\n", encoding="utf-8")
    monkeypatch.setattr(load_prompt, "MEMORY_INDEX", memory_index, raising=False)
    monkeypatch.setattr(load_prompt, "WORKDIR", tmp_path, raising=False)
    monkeypatch.setattr(
        load_prompt,
        "TOOLS_HANDLERS",
        {"shell": object(), "todo_write": object()},
        raising=False,
    )

    context = load_prompt.update_context({"old": "value"}, [{"role": "user"}])

    assert context == {
        "enabled_tools": ["shell", "todo_write"],
        "workspace": str(tmp_path),
        "memories": "Persistent project note",
    }


def test_update_context_uses_empty_memories_when_index_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(load_prompt, "MEMORY_INDEX", tmp_path / "missing.md", raising=False)
    monkeypatch.setattr(load_prompt, "WORKDIR", tmp_path, raising=False)
    monkeypatch.setattr(load_prompt, "TOOLS_HANDLERS", {}, raising=False)

    context = load_prompt.update_context({}, [])

    assert context == {
        "enabled_tools": [],
        "workspace": str(tmp_path),
        "memories": "",
    }


def test_update_context_prefers_explicit_runtime_memory_index(monkeypatch, tmp_path):
    legacy_index = tmp_path / "legacy" / "MEMORY.md"
    runtime_index = tmp_path / "runtime" / "MEMORY.md"
    legacy_index.parent.mkdir()
    runtime_index.parent.mkdir()
    legacy_index.write_text("legacy memory", encoding="utf-8")
    runtime_index.write_text("runtime memory", encoding="utf-8")
    monkeypatch.setattr(load_prompt, "MEMORY_INDEX", legacy_index, raising=False)
    monkeypatch.setattr(load_prompt, "WORKDIR", tmp_path, raising=False)
    monkeypatch.setattr(load_prompt, "TOOLS_HANDLERS", {}, raising=False)

    context = load_prompt.update_context({}, [], memory_index=runtime_index)

    assert context["memories"] == "runtime memory"
