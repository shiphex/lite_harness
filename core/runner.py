"""Agent 单轮执行入口。

本模块负责组织一次完整 Agent run 的外围生命周期，包括提交用户输入、
运行 ``UserPromptSubmit`` Hook、重置运行状态并进入统一的 ``query_loop``。
Master、subagent 和 teammate 都应通过该入口执行任务，避免各自维护重复流程。

Typical usage example:
    state, status = run_turn(runtime, "分析当前模块")
"""

import hook

from .loop import query_loop
from .runtime import AgentRuntime


def run_turn(
    runtime: AgentRuntime,
    user_input: str,
):
    """执行一个完整的 Agent run。

    Args:
        runtime: 执行本轮任务的 Agent Runtime。
        user_input: 需要追加到 Runtime history 的输入文本。

    Returns:
        tuple: ``query_loop`` 返回的 ``(state, status)``。

    Raises:
        Exception: Hook、模型调用或工具执行产生且未被下层恢复的异常。
    """

    runtime.hooks.run(
        hook.HookEvent.USER_PROMPT_SUBMIT,
        hook.make_hook_context(runtime),
        user_input,
    )

    runtime.state.messages.append({
        "role": "user",
        "content": user_input,
    })

    # 每次外部输入都代表一个新的 run，必须先清理上一轮的瞬时状态。
    runtime.begin_run()
    return query_loop(runtime)
