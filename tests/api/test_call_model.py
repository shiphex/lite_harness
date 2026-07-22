import api


def test_call_model(capsys):
    response = api.call_model(messages = [{"role": "user", "content": "你好"}])

    # 显式读取被拦截的输出并打印（或者对其进行断言）
    print(response.content)
    captured = capsys.readouterr()
    with capsys.disabled():
        print(f"\n捕获到的内容：{captured.out}")
    
    assert response is not None
