from types import SimpleNamespace

import pytest

from tools.tool_class import ToolContext
from tools.tool_handler import ToolExecutor


def test_execute_forwards_context_to_handler(tmp_path):
    runtime = SimpleNamespace(name="runtime")
    context = ToolContext(runtime)
    calls = []

    def handler(received_context, value):
        calls.append((received_context, value))
        return "ok"

    executor = ToolExecutor(
        registry={"demo": handler},
        allowed_tools=[{"name": "demo"}],
        workspace=tmp_path,
    )

    assert executor.execute(context, "demo", {"value": 3}) == "ok"
    assert calls == [(context, 3)]


def test_execute_rejects_tool_not_in_allowlist(tmp_path):
    executor = ToolExecutor(
        registry={"demo": lambda context: "ok"},
        allowed_tools=[],
        workspace=tmp_path,
    )

    with pytest.raises(PermissionError, match="Tool not allowed"):
        executor.execute(ToolContext(SimpleNamespace()), "demo", {})


def test_execute_returns_unknown_for_missing_handler(tmp_path):
    executor = ToolExecutor(
        registry={},
        allowed_tools=[{"name": "missing"}],
        workspace=tmp_path,
    )

    assert executor.execute(ToolContext(SimpleNamespace()), "missing", {}) == (
        "Unknown: missing"
    )
