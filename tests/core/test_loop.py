import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import core.loop as loop


def test_agent_loop_compact_replaces_history_with_tool_result(monkeypatch):
    messages = [{"role": "user", "content": "please compact"}]
    context = {"memories": ""}
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
    monkeypatch.setattr(loop.tools, "estimate_size", lambda value: 0)
    monkeypatch.setattr(loop.builtin, "load_memories", lambda messages: "")
    monkeypatch.setattr(loop.builtin, "get_system_prompt", lambda context: "system prompt")
    monkeypatch.setattr(loop.builtin, "update_context", lambda context, messages: context)
    monkeypatch.setattr(loop.builtin, "extract_memories", lambda messages: None)
    monkeypatch.setattr(loop.builtin, "consolidate_memories", lambda: None)
    monkeypatch.setattr(
        loop.tools,
        "compact_history",
        lambda value: [{"role": "user", "content": "[已压缩]\n\nsummary"}],
    )
    monkeypatch.setattr(loop.hook, "trigger_hooks", lambda *args: None)
    monkeypatch.setattr(loop.cli, "put_agent_other_info", lambda *args: None)

    loop.agent_loop(messages, context)

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


def test_agent_loop_refreshes_context_after_tool_result(monkeypatch):
    messages = [{"role": "user", "content": "use a tool"}]
    context = {"memories": ""}
    system_prompts = []
    tool_block = SimpleNamespace(
        type="tool_use",
        name="demo_tool",
        id="tool-demo",
        input={"query": "hello"},
    )
    final_text = SimpleNamespace(type="text", text="done")

    responses = [
        SimpleNamespace(stop_reason="tool_use", content=[tool_block]),
        SimpleNamespace(stop_reason="end_turn", content=[final_text]),
    ]

    def fake_call_model(**kwargs):
        system_prompts.append(kwargs["system_prompt"])
        return responses.pop(0)

    def fake_get_system_prompt(value):
        return "refreshed system prompt" if value.get("refreshed") else "initial system prompt"

    def fake_update_context(value, current_messages):
        assert value is context
        assert current_messages[-1] == {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tool-demo",
                    "content": "tool output",
                }
            ],
        }
        return {"refreshed": True}

    monkeypatch.setattr(loop.api, "call_model", fake_call_model)
    monkeypatch.setattr(loop.tools, "TOOLS_LIST", [{"name": "demo_tool"}])
    monkeypatch.setattr(loop.tools, "tool_result_budget", lambda value: value)
    monkeypatch.setattr(loop.tools, "snip_compact", lambda value: value)
    monkeypatch.setattr(loop.tools, "micro_compact", lambda value: value)
    monkeypatch.setattr(loop.tools, "estimate_size", lambda value: 0)
    monkeypatch.setattr(loop.tools, "call_tool", lambda name, input: "tool output")
    monkeypatch.setattr(loop.builtin, "load_memories", lambda messages: "")
    monkeypatch.setattr(loop.builtin, "get_system_prompt", fake_get_system_prompt)
    monkeypatch.setattr(loop.builtin, "update_context", fake_update_context)
    monkeypatch.setattr(loop.builtin, "extract_memories", lambda messages: None)
    monkeypatch.setattr(loop.builtin, "consolidate_memories", lambda: None)
    monkeypatch.setattr(loop.hook, "trigger_hooks", lambda *args: None)
    monkeypatch.setattr(loop.cli, "put_agent_other_info", lambda *args: None)

    loop.agent_loop(messages, context)

    assert system_prompts == ["initial system prompt", "refreshed system prompt"]
