from types import SimpleNamespace

import tools.file_option as file_option
from tools.tool_class import ToolContext


def context():
    return ToolContext(SimpleNamespace())


def test_run_read(tmp_path, monkeypatch):
    monkeypatch.setattr(file_option, "WORKDIR", tmp_path)
    (tmp_path / "sample.txt").write_text("one\ntwo\n", encoding="utf-8")

    result = file_option.run_read(context(), "sample.txt", limit=1)

    assert result.startswith("one\n")
    assert "还有 1" in result


def test_run_write(tmp_path, monkeypatch):
    monkeypatch.setattr(file_option, "WORKDIR", tmp_path)

    result = file_option.run_write(context(), "sample.txt", "test file write.")

    assert result != ""
    assert (tmp_path / "sample.txt").read_text(encoding="utf-8") == "test file write."


def test_run_edit(tmp_path, monkeypatch):
    monkeypatch.setattr(file_option, "WORKDIR", tmp_path)
    target = tmp_path / "sample.txt"
    target.write_text("test file write.", encoding="utf-8")

    result = file_option.run_edit(context(), "sample.txt", "write", "edit")

    assert result != ""
    assert target.read_text(encoding="utf-8") == "test file edit."


def test_run_glob(tmp_path, monkeypatch):
    monkeypatch.setattr(file_option, "WORKDIR", tmp_path)
    (tmp_path / "sample.py").write_text("", encoding="utf-8")

    assert file_option.run_glob(context(), "*.py") == "sample.py"
