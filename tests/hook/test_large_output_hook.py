from types import SimpleNamespace

from hook import large_output_hook as module


def test_large_output_hook_logs_only_above_threshold(monkeypatch):
    debug_calls = []
    monkeypatch.setattr(module.logger, "debug", lambda *args: debug_calls.append(args))

    threshold = module.config.Config().get_content_length()[
        "MAX_INLINE_TOOL_RESULT_TOKENS"
    ]
    block = SimpleNamespace(name="powershell")

    assert module.large_output_hook(None, block, "x" * threshold) is None
    assert debug_calls == []

    assert module.large_output_hook(None, block, "x" * (threshold + 1)) is None
    assert len(debug_calls) == 1
    assert debug_calls[0][0].startswith("[HOOK] powershell")
