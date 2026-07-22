from hook import large_output_hook
from types import SimpleNamespace


def test_large_output_hook(capsys):
    # 1. 测试输出长度小于等于 4096 个字符的情况
    block = SimpleNamespace(
        name = "powershell",
        output = {"command": "rm test.txt"},
    )
    result = large_output_hook.large_output_hook(block, block.output)
    # 获取终端捕获到的标准输出和标准错误
    captured = capsys.readouterr()
    assert result is None
    # 断言终端输出的内容是否符合预期
    # 注意：print() 默认会自带换行符 \n，所以断言时要加上 \n
    assert captured.out == ""

    # 2. 测试输出长度超过 4096 个字符的情况
    block = SimpleNamespace(
        name = "powershell",
        output = "testoutput" * 500,
    )
    result = large_output_hook.large_output_hook(block, block.output)
    # 获取终端捕获到的标准输出和标准错误
    captured = capsys.readouterr()
    assert result is None
    # 断言终端输出的内容是否符合预期
    # 注意：print() 默认会自带换行符 \n，所以断言时要加上 \n
    assert captured.out == "\033[33m⚠ powershell 输出过大，长度为 5000。\033[0m\n"
