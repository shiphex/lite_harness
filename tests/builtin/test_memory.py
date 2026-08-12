import json
from types import SimpleNamespace

import builtin.memory as memory
from api.contract import ModelResponse, TextPart


def _block(text: str, block_type: str = "text"):
    return SimpleNamespace(type=block_type, text=text)


def _model_response(text: str):
    return ModelResponse(content=[TextPart(text)], stop_reason="end_turn")


def _runtime(model="fake-memory-model"):
    return SimpleNamespace(
        policy=SimpleNamespace(
            model={"api": "fake", "model_name": model},
            tools_list=[{"name": "write_file"}],
        )
    )


def _manager(tmp_path, mode=memory.MemoryMode.READ_WRITE):
    return memory.MemoryManager(
        root=tmp_path / "memory",
        policy=memory.MemoryPolicy(mode=mode, namespace="test"),
    )


def _write_items(manager, count):
    for index in range(count):
        memory.write_memory_file(
            manager,
            name=f"old-{index}",
            mem_type="project",
            desc=f"Old {index}",
            body=f"Old body {index}",
        )


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


def test_read_write_initialization_respects_memory_mode(tmp_path):
    manager = _manager(tmp_path)
    assert manager.root.is_dir()
    assert not manager.index_path.exists()

    read_only = _manager(tmp_path / "read-only", memory.MemoryMode.READ_ONLY)
    assert not read_only.root.exists()
    assert memory.write_memory_file(read_only, "x", "user", "x", "x") is None


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

    path = memory.write_memory_file(
        manager,
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


def test_memory_names_and_reads_cannot_escape_namespace(tmp_path):
    manager = _manager(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("secret", encoding="utf-8")

    path = memory.write_memory_file(
        manager,
        name="../outside\\memory",
        mem_type="user",
        desc="safe",
        body="content",
    )

    assert path.parent == manager.root
    assert path.is_file()
    assert memory.read_memory_file(manager, "../outside.md") is None


def test_load_reads_selected_memory_file_with_runtime(tmp_path, monkeypatch):
    manager = _manager(tmp_path)
    memory.write_memory_file(manager, "alpha", "project", "Alpha", "Alpha body")
    memory.write_memory_file(manager, "beta", "project", "Beta", "Beta body")
    monkeypatch.setattr(
        memory,
        "select_relevant_memories",
        lambda current_manager, runtime, messages: ["alpha.md", "beta.md"],
    )

    result = manager.load(_runtime(), [{"role": "user", "content": "hello"}])

    assert result == (
        "<relevant_memories>\n\n"
        "---\nname: alpha\ndescription: Alpha\n"
        "type: project\n---\n\nbody: Alpha body\n\n\n"
        "---\nname: beta\ndescription: Beta\n"
        "type: project\n---\n\nbody: Beta body\n\n\n"
        "</relevant_memories>"
    )


def test_extract_memories_uses_runtime_model_and_returns_success(tmp_path, monkeypatch):
    manager = _manager(tmp_path)
    requests = []

    def fake_adapter(_config):
        return SimpleNamespace(
            complete=lambda request: requests.append(request) or _model_response(
                json.dumps([{
                    "name": "project-detail",
                    "type": "project",
                    "description": "Project uses pytest",
                    "body": "Tests should use pytest fixtures.",
                }])
            )
        )

    monkeypatch.setattr(memory, "create_adapter", fake_adapter)

    assert manager.extract(
        _runtime(),
        [{"role": "user", "content": "This project uses pytest."}],
    ) is True
    assert requests[0].model == "fake-memory-model"
    assert requests[0].tools == []
    assert (manager.root / "project-detail.md").is_file()


def test_extract_memories_reports_model_failure_without_files(tmp_path, monkeypatch, capsys):
    manager = _manager(tmp_path)
    monkeypatch.setattr(
        memory,
        "create_adapter",
        lambda config: (_ for _ in ()).throw(RuntimeError("model unavailable")),
    )

    assert manager.extract(
        _runtime(),
        [{"role": "user", "content": "Remember tabs."}],
    ) is False
    assert list(manager.root.glob("*.md")) == []
    assert "model unavailable" in capsys.readouterr().out


def test_consolidate_replaces_files_after_success(tmp_path, monkeypatch):
    manager = _manager(tmp_path)
    _write_items(manager, memory.CONSOLIDATE_THRESHOLD)
    monkeypatch.setattr(
        memory,
        "create_adapter",
        lambda config: SimpleNamespace(
            complete=lambda request: _model_response(json.dumps([{
                "name": "merged-memory",
                "type": "user",
                "description": "Merged memory",
                "body": "Merged body.",
            }]))
        ),
    )

    assert manager.consolidate(_runtime()) is True
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
    monkeypatch.setattr(
        memory,
        "create_adapter",
        lambda config: (_ for _ in ()).throw(RuntimeError("summary unavailable")),
    )

    assert manager.consolidate(_runtime()) is False
    after = {
        path.name: path.read_text(encoding="utf-8")
        for path in manager.root.glob("*.md")
    }
    assert after == before
    assert "summary unavailable" in capsys.readouterr().out
