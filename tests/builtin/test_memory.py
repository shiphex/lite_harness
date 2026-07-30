import importlib
import sys
import types
from types import SimpleNamespace


_fake_api = types.ModuleType("api")
_fake_api.call_model = lambda *args, **kwargs: None

_previous_api = sys.modules.get("api")
sys.modules["api"] = _fake_api
memory = importlib.import_module("builtin.memory")
if _previous_api is None:
    del sys.modules["api"]
else:
    sys.modules["api"] = _previous_api


def _block(text: str, block_type: str = "text"):
    return SimpleNamespace(type=block_type, text=text)


def _model_response(text: str):
    return SimpleNamespace(content=[_block(text)])


def _use_tmp_memory_dir(monkeypatch, tmp_path):
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    memory_index = memory_dir / "MEMORY.md"
    monkeypatch.setattr(memory, "MEMORY_DIR", memory_dir)
    monkeypatch.setattr(memory, "MEMORY_INDEX", memory_index)
    return memory_dir, memory_index


def test_parse_frontmatter_returns_meta_and_body():
    raw = """---
name: user-tabs
description: User prefers tabs
type: user
---

Use tabs for indentation.
"""

    meta, body = memory._parse_frontmatter(raw)

    assert meta == {
        "name": "user-tabs",
        "description": "User prefers tabs",
        "type": "user",
    }
    assert body == "Use tabs for indentation."


def test_parse_frontmatter_returns_original_text_without_frontmatter():
    raw = "Plain memory body."

    meta, body = memory._parse_frontmatter(raw)

    assert meta == {}
    assert body == raw


def test_extract_text_joins_text_blocks_and_stringifies_non_lists():
    content = [_block("hello"), _block("ignored", "tool_use"), _block("world")]

    assert memory.extract_text(content) == "hello\nworld"
    assert memory.extract_text("plain text") == "plain text"


def test_read_memory_file_returns_content_or_none(monkeypatch, tmp_path):
    memory_dir, _ = _use_tmp_memory_dir(monkeypatch, tmp_path)
    (memory_dir / "known.md").write_text("remember this", encoding="utf-8")

    assert memory.read_memory_file("known.md") == "remember this"
    assert memory.read_memory_file("missing.md") is None


def test_list_memory_files_reads_metadata(monkeypatch, tmp_path):
    memory_dir, _ = _use_tmp_memory_dir(monkeypatch, tmp_path)
    (memory_dir / "alpha.md").write_text(
        "---\nname: alpha\ndescription: Alpha memory\ntype: project\n---\n\nAlpha body",
        encoding="utf-8",
    )
    (memory_dir / "beta.md").write_text("Beta body", encoding="utf-8")
    (memory_dir / "Memory.md").write_text("Index should be ignored", encoding="utf-8")

    files = memory.list_memory_files()

    assert files == [
        {
            "filename": "alpha.md",
            "name": "alpha",
            "description": "Alpha memory",
            "type": "project",
            "body": "Alpha body",
        },
        {
            "filename": "beta.md",
            "name": "beta",
            "description": "",
            "type": "user",
            "body": "Beta body",
        },
    ]


def test_select_relevant_memories_uses_model_indices(monkeypatch, tmp_path):
    memory_dir, _ = _use_tmp_memory_dir(monkeypatch, tmp_path)
    (memory_dir / "alpha.md").write_text(
        "---\nname: alpha\ndescription: Alpha memory\n---\n\nAlpha body",
        encoding="utf-8",
    )
    (memory_dir / "beta.md").write_text(
        "---\nname: beta\ndescription: Beta memory\n---\n\nBeta body",
        encoding="utf-8",
    )

    def fake_call_model(messages, model_pattern):
        assert model_pattern == "mini"
        assert "最近的对话" in messages[0]["content"]
        return _model_response("selected memories: [1, 99, 0]")

    monkeypatch.setattr(memory.api, "call_model", fake_call_model)

    messages = [{"role": "user", "content": "Need beta and alpha context."}]

    assert memory.select_relevant_memories(messages, max_items=2) == ["beta.md", "alpha.md"]


def test_select_relevant_memories_falls_back_to_keywords(monkeypatch, tmp_path):
    memory_dir, _ = _use_tmp_memory_dir(monkeypatch, tmp_path)
    (memory_dir / "python.md").write_text(
        "---\nname: python-style\ndescription: pytest fixtures\n---\n\nUse pytest.",
        encoding="utf-8",
    )
    (memory_dir / "ui.md").write_text(
        "---\nname: ui-style\ndescription: buttons and panels\n---\n\nUI notes.",
        encoding="utf-8",
    )

    def failing_call_model(*args, **kwargs):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(memory.api, "call_model", failing_call_model)

    messages = [{"role": "user", "content": "Please add pytest coverage for python code."}]

    assert memory.select_relevant_memories(messages) == ["python.md"]


def test_load_memories_wraps_selected_file_contents(monkeypatch, tmp_path):
    memory_dir, _ = _use_tmp_memory_dir(monkeypatch, tmp_path)
    (memory_dir / "alpha.md").write_text("Alpha body", encoding="utf-8")
    (memory_dir / "beta.md").write_text("Beta body", encoding="utf-8")
    monkeypatch.setattr(memory, "select_relevant_memories", lambda messages: ["alpha.md", "beta.md"])

    result = memory.load_memories([{"role": "user", "content": "hello"}])

    assert result == "<relevant_memories>\n\nAlpha body\n\nBeta body\n\n</relevant_memories>"


def test_write_memory_file_writes_frontmatter_and_rebuilds_index(monkeypatch, tmp_path):
    memory_dir, memory_index = _use_tmp_memory_dir(monkeypatch, tmp_path)

    path = memory.write_memory_file(
        name="User Preference",
        mem_type="user",
        desc="Prefers concise answers",
        body="Keep responses short.",
    )

    assert path == memory_dir / "user-preference.md"
    assert path.read_text(encoding="utf-8") == (
        "---\n"
        "name: User Preference\n"
        "description: Prefers concise answers\n"
        "type: user\n"
        "---\n\n"
        "body: Keep responses short.\n"
    )
    assert memory_index.read_text(encoding="utf-8") == (
        "- [User Preference](user-preference.md) - Prefers concise answers\n"
    )


def test_extract_memories_writes_items_from_model_response(monkeypatch, tmp_path):
    memory_dir, memory_index = _use_tmp_memory_dir(monkeypatch, tmp_path)

    def fake_call_model(messages, model_pattern):
        assert model_pattern == "mini"
        assert "对话内容" in messages[0]["content"]
        return _model_response(
            """
[
  {
    "name": "project-detail",
    "type": "project",
    "description": "Project uses pytest",
    "body": "Tests should use pytest fixtures."
  }
]
"""
        )

    monkeypatch.setattr(memory.api, "call_model", fake_call_model)

    memory.extract_memories([{"role": "user", "content": "This project uses pytest."}])

    path = memory_dir / "project-detail.md"
    assert path.exists()
    assert "description: Project uses pytest" in path.read_text(encoding="utf-8")
    assert memory_index.read_text(encoding="utf-8") == (
        "- [project-detail](project-detail.md) - Project uses pytest\n"
    )


def test_extract_memories_warns_when_model_call_fails(monkeypatch, tmp_path, capsys):
    memory_dir, _ = _use_tmp_memory_dir(monkeypatch, tmp_path)

    def failing_call_model(*args, **kwargs):
        raise RuntimeError("mini model unavailable")

    monkeypatch.setattr(memory.api, "call_model", failing_call_model)

    memory.extract_memories([{"role": "user", "content": "Remember that I use tabs."}])

    captured = capsys.readouterr()
    assert "[Memory: 提取失败] mini model unavailable" in captured.out
    assert list(memory_dir.glob("*.md")) == []


def test_consolidate_memories_rewrites_memory_files(monkeypatch, tmp_path):
    memory_dir, memory_index = _use_tmp_memory_dir(monkeypatch, tmp_path)
    for idx in range(memory.CONSOLIDATE_THRESHOLD):
        (memory_dir / f"old-{idx}.md").write_text(
            f"---\nname: old-{idx}\ndescription: Old {idx}\n---\n\nOld body {idx}",
            encoding="utf-8",
        )
    memory_index.write_text("existing index", encoding="utf-8")

    def fake_call_model(messages, model_pattern):
        assert model_pattern == "summary"
        assert "合并以下记忆文件" in messages[0]["content"]
        return _model_response(
            """
[
  {
    "name": "merged-memory",
    "type": "user",
    "description": "Merged memory",
    "body": "Merged body."
  }
]
"""
        )

    monkeypatch.setattr(memory.api, "call_model", fake_call_model)

    memory.consolidate_memories()

    md_files = sorted(path.name for path in memory_dir.glob("*.md"))
    assert md_files == ["MEMORY.md", "merged-memory.md"]
    assert (memory_dir / "merged-memory.md").read_text(encoding="utf-8").startswith(
        "---\nname: merged-memory\n"
    )
    assert memory_index.read_text(encoding="utf-8") == (
        "- [merged-memory](merged-memory.md) - Merged memory\n"
    )
