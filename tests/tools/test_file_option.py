import tools.file_option as file_option


def test_run_read():
    result = file_option.run_read(path="config/config.py")

    assert result != ""


def test_run_write(tmp_path, monkeypatch):
    monkeypatch.setattr(file_option, "WORKDIR", tmp_path)

    result = file_option.run_write(path="sample.txt", content="test file write.")

    assert result != ""
    assert (tmp_path / "sample.txt").read_text(encoding="utf-8") == "test file write."


def test_run_edit(tmp_path, monkeypatch):
    monkeypatch.setattr(file_option, "WORKDIR", tmp_path)
    target = tmp_path / "sample.txt"
    target.write_text("test file write.", encoding="utf-8")

    result = file_option.run_edit(path="sample.txt", old_text="write", new_text="edit")

    assert result != ""
    assert target.read_text(encoding="utf-8") == "test file edit."


def test_run_glob():
    result = file_option.run_glob(pattern="*.py")

    assert result != ""
