import importlib.util
from pathlib import Path


def _load_module_from_path(module_name: str, relative_path: str):
    module_path = Path(__file__).parents[2] / relative_path
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
