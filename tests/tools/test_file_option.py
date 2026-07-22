from tools.file_option import run_read, run_write, run_edit, run_glob


def test_run_read(capsys):
    result = run_read(path="config/config.py")

    # 显式读取被拦截的输出并打印（或者对其进行断言）
    print(result[:100])
    captured = capsys.readouterr()
    with capsys.disabled():
        print(f"\n捕获到的内容：{captured.out}")

    assert result != ""


def test_run_write(capsys):
    result = run_write(path="test.txt", content="test file write.")
    print(result)
    captured = capsys.readouterr()
    with capsys.disabled():
        print(f"\n捕获到的内容：{captured.out}")

    assert result != ""


def test_run_edit(capsys):
    result = run_edit(path="test.txt", old_text="write", new_text="edit")
    print(result)
    captured = capsys.readouterr()
    with capsys.disabled():
        print(f"\n捕获到的内容：{captured.out}")

    assert result != ""


def test_run_glob(capsys):
    result = run_glob(pattern="*.py")
    print(result)
    captured = capsys.readouterr()
    with capsys.disabled():
        print(f"\n捕获到的内容：{captured.out}")

    assert result != ""