"""复用现有 AgentRuntime / query_loop 的 TeamAgent execution wrapper。"""

from collections.abc import Callable
from typing import Any, TYPE_CHECKING

import hook

from .contracts import TeamError

if TYPE_CHECKING:
    from core.runtime import AgentRuntime


RunLoop = Callable[["AgentRuntime"], tuple[Any, Any]]


class TeamAgent:
    """被动持有一个 AgentRuntime，并提供统一的单次执行入口。"""

    def __init__(
        self,
        *,
        runtime: "AgentRuntime",
        run_loop: RunLoop | None = None,
    ):
        if run_loop is None:
            from core.loop import query_loop

            run_loop = query_loop
        self.runtime = runtime
        self._run_loop = run_loop

    def run(self, prompt: str):
        """把一次输入交给现有 query_loop，不创建第二套 Agent Loop。"""

        if not isinstance(prompt, str) or not prompt.strip():
            raise TeamError("prompt 必须是非空字符串")

        self.runtime.hooks.run(
            hook.HookEvent.USER_PROMPT_SUBMIT,
            hook.make_hook_context(self.runtime),
            prompt,
        )
        self.runtime.state.messages.append({"role": "user", "content": prompt})
        self.runtime.begin_run()
        return self._run_loop(self.runtime)
