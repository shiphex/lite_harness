from dataclasses import dataclass
from typing import Protocol, Any


@dataclass(slots=True, frozen=True)
class ApprovalRequest:
    tool_call_id: str
    tool_name: str
    arguments: dict[str, Any]
    reason: str


@dataclass(slots=True, frozen=True)
class ApprovalResponse:
    approved: bool
    # message: str | None = None


class Interaction(Protocol):

    def request_approval(
        self,
        request: ApprovalRequest,
    ) -> ApprovalResponse:
        ...


class NonInteractiveInteraction:

    def request_approval(
        self,
        request: ApprovalRequest,
    ) -> ApprovalResponse:

        return ApprovalResponse(
            approved=False,
        )