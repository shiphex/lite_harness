import tools.load_skill as load_skill
from types import SimpleNamespace

from tools.tool_class import ToolContext


def test_parse_frontmatter_with_metadata():
    raw = "---\nname: demo-skill\ndescription: Demo skill\n---\n# Demo\nSkill body.\n"

    meta, body = load_skill._parse_frontmatter(raw)

    assert meta == {"name": "demo-skill", "description": "Demo skill"}
    assert body == "# Demo\nSkill body."


def test_scan_skill_registers_skill_from_configured_skill_dir(tmp_path, monkeypatch):
    skill_dir = tmp_path / "skills"
    demo_dir = skill_dir / "demo"
    demo_dir.mkdir(parents=True)
    raw = "---\nname: demo-skill\ndescription: Demo skill\n---\n# Demo\nSkill body.\n"
    (demo_dir / "SKILL.md").write_text(raw, encoding="utf-8")

    class FakeConfig:
        def get_path_config(self, path_name):
            assert path_name == "skill_dir"
            return skill_dir

    monkeypatch.setattr(load_skill.config, "Config", FakeConfig)
    monkeypatch.setattr(load_skill, "SKILL_REGISTRY", {})

    load_skill._scan_skill()

    assert load_skill.SKILL_REGISTRY["demo-skill"]["content"] == raw


def test_load_skill_accepts_context_and_returns_content(monkeypatch):
    monkeypatch.setattr(
        load_skill,
        "SKILL_REGISTRY",
        {"demo": {"content": "full skill content"}},
    )

    assert load_skill.load_skill(ToolContext(SimpleNamespace()), "demo") == (
        "full skill content"
    )


def test_load_skill_returns_message_for_missing_skill(monkeypatch):
    monkeypatch.setattr(load_skill, "SKILL_REGISTRY", {})

    assert "missing" in load_skill.load_skill(
        ToolContext(SimpleNamespace()),
        "missing",
    )
