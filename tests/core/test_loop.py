from types import SimpleNamespace

import core.loop as loop


def test_agent_loop_compact_replaces_history_with_tool_result(monkeypatch):
    messages = [{"role": "user", "content": "please compact"}]
    calls = []
    compact_tool = SimpleNamespace(
        type="tool_use",
        name="compact",
        id="tool-compact",
        input={},
    )
    final_text = SimpleNamespace(type="text", text="done")

    responses = [
        SimpleNamespace(stop_reason="tool_use", content=[compact_tool]),
        SimpleNamespace(stop_reason="end_turn", content=[final_text]),
    ]

    def fake_call_model(**kwargs):
        calls.append(kwargs["messages"].copy())
        return responses.pop(0)

    monkeypatch.setattr(loop.api, "call_model", fake_call_model)
    monkeypatch.setattr(loop.tools, "tool_result_budget", lambda value: value)
    monkeypatch.setattr(loop.tools, "snip_compact", lambda value: value)
    monkeypatch.setattr(loop.tools, "micro_compact", lambda value: value)
    monkeypatch.setattr(loop.builtin, "load_memories", lambda messages: "")
    monkeypatch.setattr(loop.builtin, "build_system", lambda: "system prompt")
    monkeypatch.setattr(loop.builtin, "extract_memories", lambda messages: None)
    monkeypatch.setattr(loop.builtin, "consolidate_memories", lambda: None)
    monkeypatch.setattr(
        loop.tools,
        "compact_history",
        lambda value: [{"role": "user", "content": "[已压缩]\n\nsummary"}],
    )
    monkeypatch.setattr(loop.hook, "trigger_hooks", lambda *args: None)
    monkeypatch.setattr(loop.cli, "put_agent_other_info", lambda *args: None)

    loop.agent_loop(messages)

    assert messages == [
        {"role": "user", "content": "[已压缩]\n\nsummary"},
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tool-compact",
                    "content": "[已压缩： 对话历史已生成摘要。]",
                }
            ],
        },
        {"role": "assistant", "content": [final_text]},
    ]
    assert calls[1] == [
        {"role": "user", "content": "[已压缩]\n\nsummary"},
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tool-compact",
                    "content": "[已压缩： 对话历史已生成摘要。]",
                }
            ],
        },
    ]
