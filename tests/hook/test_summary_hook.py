from hook import summary_hook as module


def test_summary_hook_logs_tool_count_without_cli_output(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(module.logger, "debug", lambda *args: calls.append(args))
    messages = [
        {"role": "assistant", "content": []},
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "1", "content": "ok"},
                {"type": "tool_result", "tool_use_id": "2", "content": "ok"},
            ],
        },
    ]

    assert module.summary_hook(None, messages) is None
    assert len(calls) == 1
    assert "2" in calls[0][0]
    assert capsys.readouterr().out == ""
