from hook.summary_hook import summary_hook

def test_summary_hook(capsys):
    messages = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！"},
        {"role": "tool", "content": [{"type": "tool_result", "name": "powershell", "input": {"command": "ls"}}]},
    ]
    result = summary_hook(messages)
    tool_count = sum(1 for m in messages 
                     for b in (m.get("content") if isinstance(m.get("content"), list) else [])
                     if isinstance(b, dict) and b.get("type") == "tool_result")
    # 获取终端捕获到的标准输出和标准错误
    captured = capsys.readouterr()
    assert result is None
    assert captured.out == f"\033[90m● [HOOK] Stop: session used {tool_count} tool calls.\033[0m\n"
