from hook import context_inject_hook as module


def test_context_inject_hook_logs_metadata_without_raw_query(monkeypatch):
    calls = []
    monkeypatch.setattr(module.logger, "debug", lambda *args: calls.append(args))

    assert module.context_inject_hook(None, "secret token") is None

    assert calls
    assert "secret token" not in repr(calls)
    assert calls[0][0].count("%s") == 1
    assert calls[0][0].count("%d") == 1
