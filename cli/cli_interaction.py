import cli
from event.interaction import (
    ApprovalRequest,
    ApprovalResponse,
)


class CliInteraction:
    """ CLI 交互类。定义了与用户交互的接口。
    
    Methods:
        get_user_input: 获取用户输入。
        request_approval: 请求用户确认工具调用。
    
    """
    def get_user_input(
        self,
        message: str = ">> ",
    ) -> str:
        """ 获取用户输入。"""
        return cli.get_user_input(message)


    def request_approval(
        self,
        request: ApprovalRequest,
    ) -> ApprovalResponse:

        cli.inform_system_info(
            f"\n⚠ {request.reason}"
        )

        cli.inform_system_info(
            f"    Tool: "
            f"{request.tool_name}"
            f"({request.arguments})"
        )

        choice = cli.get_user_input(
            "\n    是否继续？(y/N): "
        ).strip().lower()

        return ApprovalResponse(
            approved=choice in ("y", "yes"),
        )