from types import SimpleNamespace

import tools.compact as compact


def test_block_type_supports_dict_and_object():
    assert compact._block_type({"type": "tool_use"}) == "tool_use"
    assert compact._block_type(SimpleNamespace(type="text")) == "text"
    assert compact._block_type("plain text") is None


def test_message_has_tool_use_detects_assistant_tool_block():
    message = {
        "role": "assistant",
        "content": [
            {"type": "text", "text": "hello"},
            SimpleNamespace(type="tool_use"),
        ],
    }

    assert compact._message_has_tool_use(message) is True
    assert compact._message_has_tool_use({"role": "user", "content": []}) is False
    assert compact._message_has_tool_use({"role": "assistant", "content": "text"}) is None


def test_snip_compact_returns_original_when_short_enough():
    messages = [{"role": "user", "content": str(i)} for i in range(3)]

    assert compact.snip_compact(messages, max_massages=3) is messages


def test_snip_compact_keeps_head_tail_and_inserts_placeholder():
    messages = [{"role": "user", "content": f"message-{i}"} for i in range(8)]

    result = compact.snip_compact(messages, max_massages=5)

    assert result[:3] == messages[:3]
    assert result[-2:] == messages[-2:]
    assert result[3]["role"] == "user"
    assert "3" in result[3]["content"]


def test_collect_tool_results_finds_user_tool_result_blocks():
    result_block = {
        "type": "tool_result",
        "tool_use_id": "tool-1",
        "content": "result",
    }
    messages = [
        {"role": "assistant", "content": []},
        {"role": "user", "content": [result_block, {"type": "text"}]},
    ]

    assert compact._collect_tool_results(messages) == [(1, 0, result_block)]


def test_micro_compact_replaces_only_old_large_tool_results(monkeypatch):
    monkeypatch.setattr(compact, "EARLIER_TOOL_RESULTS_MAX_LEN", 5)
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": f"tool-{i}",
                    "content": f"large-result-{i}",
                }
            ],
        }
        for i in range(4)
    ]

    result = compact.micro_compact(messages)

    assert result is messages
    assert messages[0]["content"][0]["content"] != "large-result-0"
    assert messages[1]["content"][0]["content"] == "large-result-1"
    assert messages[2]["content"][0]["content"] == "large-result-2"
    assert messages[3]["content"][0]["content"] == "large-result-3"


def test_persist_large_output_returns_inline_content_when_small(monkeypatch):
    monkeypatch.setattr(compact, "PERSIST_THRESHOLD_CHARS", 100)

    assert compact.persist_large_output("tool-1", "small") == "small"


def test_persist_large_output_writes_large_content(tmp_path, monkeypatch):
    monkeypatch.setattr(compact, "TOOL_RESULT_DIR", tmp_path)
    monkeypatch.setattr(compact, "PERSIST_THRESHOLD_CHARS", 5)

    result = compact.persist_large_output("tool-1", "large output")

    assert (tmp_path / "tool-1.txt").read_text(encoding="utf-8") == "large output"
    assert "<persisted-output>" in result
    assert "large output" in result


def test_tool_result_budget_persists_large_results(tmp_path, monkeypatch):
    monkeypatch.setattr(compact, "TOOL_RESULT_DIR", tmp_path)
    monkeypatch.setattr(compact, "PERSIST_THRESHOLD_CHARS", 5)
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tool-1",
                    "content": "large output",
                }
            ],
        }
    ]

    result = compact.tool_result_budget(messages, max_bytes=5)

    assert result is messages
    assert "<persisted-output>" in messages[0]["content"][0]["content"]
    assert (tmp_path / "tool-1.txt").exists()


def test_tool_result_budget_ignores_non_tool_result_tail():
    messages = [{"role": "assistant", "content": "hello"}]

    assert compact.tool_result_budget(messages, max_bytes=1) is messages


def test_write_transcript_writes_json_lines(tmp_path, monkeypatch):
    monkeypatch.setattr(compact, "TRANSCRIPT_DIR", tmp_path)
    monkeypatch.setattr(compact.time, "time", lambda: 123)
    messages = [{"role": "user", "content": "hello"}]

    path = compact.write_transcript(messages)

    assert path == tmp_path / "transcript_123.txt"
    assert '"role": "user"' in path.read_text(encoding="utf-8")


def test_summarize_history_calls_model_in_summary_mode(monkeypatch):
    calls = []

    def fake_call_model(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            content=[
                SimpleNamespace(type="text", text="summary text"),
                SimpleNamespace(type="tool_use", text="ignored"),
            ]
        )

    monkeypatch.setattr(compact.api, "call_model", fake_call_model)

    result = compact.summarize_history([{"role": "user", "content": "hello"}])

    assert result == "summary text"
    assert calls[0]["model_pattern"] == "summary"
    assert calls[0]["messages"][0]["role"] == "user"


def test_compact_history_writes_transcript_and_returns_summary(monkeypatch):
    monkeypatch.setattr(compact, "write_transcript", lambda messages: "transcript.txt")
    monkeypatch.setattr(compact, "summarize_history", lambda messages: "summary text")

    result = compact.compact_history([{"role": "user", "content": "hello"}])

    assert len(result) == 1
    assert result[0]["role"] == "user"
    assert "summary text" in result[0]["content"]


def test_reactive_compact_keeps_recent_tail(monkeypatch):
    monkeypatch.setattr(compact, "write_transcript", lambda messages: "transcript.txt")
    monkeypatch.setattr(compact, "summarize_history", lambda messages: "summary text")
    messages = [{"role": "user", "content": f"message-{i}"} for i in range(8)]

    result = compact.reactive_compact(messages)

    assert "summary text" in result[0]["content"]
    assert result[1:] == messages[-5:]
