from hook import log_hook
from types import SimpleNamespace


def test_log_hook(capsys):
    block = SimpleNamespace(
        name = "powershell",
        input = {"values": "test_values"},
    )
    result = log_hook.log_hook(block)
    # 获取终端捕获到的标准输出和标准错误
    captured = capsys.readouterr()
    assert result is None
    # 断言终端输出的内容是否符合预期
    # 注意：print() 默认会自带换行符 \n，所以断言时要加上 \n
    assert captured.out == "\x1b[90m● [HOOK] powershell(['test_values'])\033[0m\n"