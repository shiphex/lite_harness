import pytest

from core.control import (
    RunDirective,
    SuspendRequest,
    ToolOutcome,
    normalize_tool_outcome,
)


def test_normalize_tool_outcome_preserves_new_and_legacy_results():
    request = SuspendRequest(kind="team.results", payload={"members": ["alice"]})
    outcome = ToolOutcome(
        content="waiting",
        directive=RunDirective.SUSPEND,
        suspend=request,
    )

    assert normalize_tool_outcome(outcome) is outcome
    assert normalize_tool_outcome(42) == ToolOutcome(content="42")


def test_suspend_outcome_requires_request():
    with pytest.raises(ValueError, match="必须提供 suspend request"):
        ToolOutcome(content="waiting", directive=RunDirective.SUSPEND)
