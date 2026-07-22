import cli


def test_inform_system_info(capsys):
    # 1. 执行告知系统信息
    cli.inform_system_info("系统信息")

    # 2. 获取终端捕获到的标准输出和标准错误
    captured = capsys.readouterr()

    # 3. 断言终端输出的内容是否符合预期
    # 注意：print() 默认会自带换行符 \n，所以断言时要加上 \n
    assert captured.out == "\x1b[33m系统信息\x1b[0m\n"


def test_inform_system_warning(capsys):
    # 1. 执行告知系统警告
    cli.inform_system_warning("系统警告")

    # 2. 获取终端捕获到的标准输出和标准错误
    captured = capsys.readouterr()

    # 3. 断言终端输出的内容是否符合预期
    # 注意：print() 默认会自带换行符 \n，所以断言时要加上 \n
    assert captured.out == "\x1b[31m系统警告\x1b[0m\n"


def test_get_user_input(monkeypatch):
    # 模拟用户在终端输入了 "hello" 并回车
    monkeypatch.setattr('builtins.input', lambda _: "hello")

    user_input = cli.get_user_input()
    assert isinstance(user_input, str)
    assert user_input == "hello"


def test_put_agent_output(capsys):
    # 1. 执行智能体输出
    cli.put_agent_output("智能体输出")

    # 2. 获取终端捕获到的标准输出和标准错误
    captured = capsys.readouterr()

    # 3. 断言终端输出的内容是否符合预期
    # 注意：print() 默认会自带换行符 \n，所以断言时要加上 \n
    assert captured.out == "\x1b[0m● 智能体输出\x1b[0m\n\n"


def test_put_agent_other_info(capsys):
    # 1. 执行智能体其他信息输出
    cli.put_agent_other_info("其他信息输出")

    # 2. 获取终端捕获到的标准输出和标准错误
    captured = capsys.readouterr()

    # 3. 断言终端输出的内容是否符合预期
    # 注意：print() 默认会自带换行符 \n，所以断言时要加上 \n
    assert captured.out == "\x1b[90m● 其他信息输出\x1b[0m\n"