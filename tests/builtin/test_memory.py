from types import SimpleNamespace

import builtin.memory as memory


def _block(text: str, block_type: str = "text"):
    return SimpleNamespace(type=block_type, text=text)


def _model_response(text: str):
    return SimpleNamespace(content=[_block(text)])


def _manager(tmp_path, mode=memory.MemoryMode.READ_WRITE):
    return memory.MemoryManager(
        root=tmp_path / "memory",
        policy=memory.MemoryPolicy(mode=mode, namespace="test"),
    )


def _write_items(manager, count):
    for index in range(count):
        manager._write_memory_file(
            name=f"old-{index}",
            mem_type="project",
            desc=f"Old {index}",
            body=f"Old body {index}",
            rebuild_index=False,
        )
    manager._rebuild_index()


def test_parse_frontmatter_returns_metadata_and_body():
    raw = """---
name: user-tabs
description: User prefers tabs
type: user
---

Use tabs for indentation.
"""

    metadata, body = memory._parse_frontmatter(raw)

    assert metadata == {
        "name": "user-tabs",
        "description": "User prefers tabs",
        "type": "user",
    }
    assert body == "Use tabs for indentation."


def test_extract_text_supports_dicts_and_objects():
    content = [
        {"type": "text", "text": "hello"},
        _block("ignored", "tool_use"),
        _block("world"),
    ]

    assert memory.extract_text(content) == "hello\nworld"
    assert memory.extract_text("plain text") == "plain text"


def test_read_write_initialization_creates_only_root(tmp_path):
    manager = _manager(tmp_path)

    assert manager.root.is_dir()
    assert not manager.index_path.exists()
    assert not manager.index_path.is_dir()

    read_only = _manager(tmp_path / "read-only", memory.MemoryMode.READ_ONLY)
    assert not read_only.root.exists()


def test_legacy_index_directory_is_moved_to_recoverable_backup(tmp_path):
    root = tmp_path / "memory"
    legacy_index = root / "MEMORY.md"
    legacy_index.mkdir(parents=True)
    (legacy_index / "marker.txt").write_text("legacy", encoding="utf-8")

    manager = memory.MemoryManager(
        root=root,
        policy=memory.MemoryPolicy(
            mode=memory.MemoryMode.READ_WRITE,
            namespace="test",
        ),
    )

    assert not manager.index_path.exists()
    backups = list(root.glob("MEMORY.md.legacy-dir-*"))
    assert len(backups) == 1
    assert (backups[0] / "marker.txt").read_text(encoding="utf-8") == "legacy"


def test_write_memory_file_writes_file_and_atomic_index(tmp_path):
    manager = _manager(tmp_path)

    path = manager._write_memory_file(
        name="User Preference",
        mem_type="user",
        desc="Prefers concise answers",
        body="Keep responses short.",
    )

    assert path == manager.root / "user-preference.md"
    assert path.is_file()
    assert manager.index_path.is_file()
    assert "- [User Preference](user-preference.md) - Prefers concise answers" in (
        manager.index_path.read_text(encoding="utf-8")
    )


def test_memory_names_cannot_escape_namespace(tmp_path):
    manager = _manager(tmp_path)

    path = manager._write_memory_file(
        name="../outside\\memory",
        mem_type="user",
        desc="safe",
        body="content",
    )

    assert path.parent == manager.root
    assert path.is_file()
    assert not (tmp_path / "outside.md").exists()
    assert manager._safe_slug("MEMORY") != "memory"


def test_load_reads_selected_memory_file(tmp_path, monkeypatch):
    manager = _manager(tmp_path)
    manager._write_memory_file("alpha", "project", "Alpha", "Alpha body")
    manager._write_memory_file("beta", "project", "Beta", "Beta body")
    monkeypatch.setattr(
        manager,
        "_select_relevant_memories",
        lambda messages: ["alpha.md", "beta.md"],
    )

    result = manager.load([{"role": "user", "content": "hello"}])

    assert result == (
        "<relevant_memories>\n\n"
        "---\nname: alpha\ndescription: Alpha\n"
        "type: project\n---\n\nbody: Alpha body\n\n\n"
        "---\nname: beta\ndescription: Beta\n"
        "type: project\n---\n\nbody: Beta body\n\n\n"
        "</relevant_memories>"
    )


def test_extract_memories_writes_items_and_index(tmp_path, monkeypatch):
    manager = _manager(tmp_path)
    monkeypatch.setattr(
        memory.api,
        "call_model",
        lambda **kwargs: _model_response(
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
        ),
    )

    assert manager.extract(
        [{"role": "user", "content": "This project uses pytest."}]
    ) is True
    assert (manager.root / "project-detail.md").is_file()
    assert "project-detail.md" in manager.index_path.read_text(encoding="utf-8")


def test_extract_memories_reports_model_failure_without_files(tmp_path, monkeypatch, capsys):
    manager = _manager(tmp_path)

    def failing_call_model(**kwargs):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(memory.api, "call_model", failing_call_model)

    assert manager.extract([{"role": "user", "content": "Remember tabs."}]) is False
    assert list(manager.root.glob("*.md")) == []
    assert "model unavailable" in capsys.readouterr().out


def test_consolidate_replaces_files_after_success(tmp_path, monkeypatch):
    manager = _manager(tmp_path)
    _write_items(manager, memory.CONSOLIDATE_THRESHOLD)
    monkeypatch.setattr(
        memory.api,
        "call_model",
        lambda **kwargs: _model_response(
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
        ),
    )

    assert manager.consolidate() is True
    assert sorted(path.name for path in manager.root.glob("*.md")) == [
        "MEMORY.md",
        "merged-memory.md",
    ]
    assert manager.index_path.read_text(encoding="utf-8") == (
        "- [merged-memory](merged-memory.md) - Merged memory\n"
    )


def test_consolidate_failure_preserves_existing_files(tmp_path, monkeypatch, capsys):
    manager = _manager(tmp_path)
    _write_items(manager, memory.CONSOLIDATE_THRESHOLD)
    before = {
        path.name: path.read_text(encoding="utf-8")
        for path in manager.root.glob("*.md")
    }

    def failing_call_model(**kwargs):
        raise RuntimeError("summary unavailable")

    monkeypatch.setattr(memory.api, "call_model", failing_call_model)

    assert manager.consolidate() is False
    after = {
        path.name: path.read_text(encoding="utf-8")
        for path in manager.root.glob("*.md")
    }
    assert after == before
    assert "summary unavailable" in capsys.readouterr().out
