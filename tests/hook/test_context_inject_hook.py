import config
from hook.context_inject_hook import context_inject_hook

def test_context_inject_hook(capsys):
    """ 测试 context 注入 hook 函数。 """
    query = "你好"
    result = context_inject_hook(None, query)

    # 获取终端捕获到的标准输出和标准错误
    captured = capsys.readouterr()
    assert result is None
    # 断言终端输出的内容是否符合预期
    # 注意：print() 默认会自带换行符 \n，所以断言时要加上 \n
    assert captured.out == f"\x1b[90m● [HOOK] UserPromptSubmit: working in {config.Config().get_path_config('project_path')}\033[0m\n"

