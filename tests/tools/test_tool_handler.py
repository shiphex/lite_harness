import tools

def test_call_tool(capsys):
    result = tools.call_tool("powershell", {"command": "echo 'Hello, World!'"})

    # 显式读取被拦截的输出并打印（或者对其进行断言）
    print(result)
    captured = capsys.readouterr()
    with capsys.disabled():
        print(f"\n捕获到的内容：{captured.out}")

    assert result == "Hello, World!"