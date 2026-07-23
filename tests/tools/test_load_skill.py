import importlib.util
from pathlib import Path


def _load_module_from_path(module_name: str, relative_path: str):
    module_path = Path(__file__).parents[2] / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


load_skill = _load_module_from_path("load_skill_under_test", "tools/load_skill.py")


def test_parse_frontmatter_with_metadata():
    raw = """---
name: demo-skill
description: Demo skill
---
# Demo
Skill body.
"""

    meta, body = load_skill._parse_frontmatter(raw)

    assert meta == {
        "name": "demo-skill",
        "description": "Demo skill",
    }
    assert body == "# Demo\nSkill body."


def test_parse_frontmatter_without_metadata():
    raw = "# Demo\nSkill body."

    meta, body = load_skill._parse_frontmatter(raw)

    assert meta == {}
    assert body == raw


def test_scan_skill_registers_skill_from_configured_skill_dir(tmp_path, monkeypatch):
    skill_dir = tmp_path / "skills"
    demo_dir = skill_dir / "demo"
    demo_dir.mkdir(parents=True)
    raw = """---
name: demo-skill
description: Demo skill
---
# Demo
Skill body.
"""
    (demo_dir / "SKILL.md").write_text(raw, encoding="utf-8")

    class FakeConfig:
        def get_path_config(self, path_name):
            assert path_name == "skill_dir"
            return skill_dir

    monkeypatch.setattr(load_skill.config, "Config", FakeConfig)
    monkeypatch.setattr(load_skill, "SKILL_REGISTRY", {})

    load_skill._scan_skill()

    assert load_skill.SKILL_REGISTRY == {
        "demo-skill": {
            "name": "demo-skill",
            "description": "Demo skill",
            "content": raw,
        }
    }


def test_scan_skill_ignores_missing_skill_dir(tmp_path, monkeypatch):
    missing_skill_dir = tmp_path / "missing"

    class FakeConfig:
        def get_path_config(self, path_name):
            assert path_name == "skill_dir"
            return missing_skill_dir

    monkeypatch.setattr(load_skill.config, "Config", FakeConfig)
    monkeypatch.setattr(load_skill, "SKILL_REGISTRY", {})

    load_skill._scan_skill()

    assert load_skill.SKILL_REGISTRY == {}


def test_list_skill_returns_empty_message(monkeypatch):
    monkeypatch.setattr(load_skill, "SKILL_REGISTRY", {})

    assert load_skill.list_skill() == "(没有发现 skill。)"


def test_list_skill_formats_registered_skills(monkeypatch):
    monkeypatch.setattr(
        load_skill,
        "SKILL_REGISTRY",
        {
            "alpha": {
                "name": "alpha",
                "description": "Alpha skill",
                "content": "",
            },
            "beta": {
                "name": "beta",
                "description": "Beta skill",
                "content": "",
            },
        },
    )

    assert load_skill.list_skill() == "- **alpha**: Alpha skill\n- **beta**: Beta skill"


def test_build_skill_prompt_includes_skill_catalog(monkeypatch):
    monkeypatch.setattr(load_skill, "list_skill", lambda: "- **demo**: Demo skill")

    assert load_skill.build_skill_prompt() == "当前可用的 skill 有：- **demo**: Demo skill"


def test_load_skill_returns_content_for_registered_skill(monkeypatch):
    monkeypatch.setattr(
        load_skill,
        "SKILL_REGISTRY",
        {
            "demo": {
                "name": "demo",
                "description": "Demo skill",
                "content": "full skill content",
            }
        },
    )

    assert load_skill.load_skill("demo") == "full skill content"


def test_load_skill_returns_message_for_missing_skill(monkeypatch):
    monkeypatch.setattr(load_skill, "SKILL_REGISTRY", {})

    assert load_skill.load_skill("missing") == "未找到 skill missing。"
