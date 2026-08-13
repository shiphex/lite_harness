""" 钩子系统 hook handler system

注册和触发 hook 函数，用于在不同事件触发时执行自定义操作。

Typical usage example:
    import hook
    hook.trigger_hooks("UserPromptSubmit", "你好")
    hook.trigger_hooks("PreToolUse", "ls")
    hook.trigger_hooks("PostToolUse", "ls", "ls")
    hook.trigger_hooks("Stop", ["ls"])
"""

from .context_inject_hook import context_inject_hook
from .large_output_hook import large_output_hook
from .permission_hook import permission_hook
from .log_hook import log_hook
from .summary_hook import summary_hook

from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from collections import defaultdict
from collections.abc import Callable


class HookEvent(str, Enum):
    """ 钩子事件枚举。定义了不同类型的 hook 事件。"""
    USER_PROMPT_SUBMIT = "user_prompt_submit"

    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"

    # PRE_COMPACT = "pre_compact"
    # POST_COMPACT = "post_compact"

    STOP = "stop"


@dataclass
class HookContext:
    """ 钩子上下文数据类。定义了 hook 事件触发时的上下文信息。"""
    session_id: str
    agent_id: str
    agent_name: str
    turn_count: int
    workspace: Path


@dataclass
class HookResult:
    """ 钩子结果数据类。定义了 hook 事件触发时的结果。"""
    blocked: bool = True
    message: str | None = None
    # modified_input: dict | None = None


def make_hook_context(runtime) -> HookContext:
    """ 创建 hook 上下文。

    从运行时状态中提取上下文信息，创建 hook 上下文对象。
    
    Args:
        runtime (Runtime): 运行时状态对象，包含会话、智能体、状态等信息。
    
    Returns:
        HookContext: 包含会话、智能体、状态等信息的 hook 上下文对象。
    """
    return HookContext(
        session_id=runtime.session_id,
        agent_id=runtime.agent_id,
        agent_name=runtime.agent_name,
        turn_count=runtime.state.turn_count,
        workspace=runtime.paths.workspace,
    )


class HookManager:
    """ 钩子管理器。用于注册和触发 hook 函数。"""
    def __init__(self):
        self._hooks = defaultdict(list)

    def register(
        self,
        event: HookEvent,
        callback: Callable,
    ) -> None:
        self._hooks[event].append(callback)

    def run(
        self,
        event: HookEvent,
        ctx: HookContext,
        *args,
    ) -> HookResult:

        for callback in self._hooks[event]:
            result = callback(ctx, *args)

            if result is None:
                continue

            if result.blocked:
                return result

        return HookResult()


def create_default_hooks() -> HookManager:
    """ 创建默认的 hook 函数。

    注册默认的 hook 函数，用于在不同事件触发时执行自定义操作。

    Returns:
        HookManager: 包含默认 hook 函数的 hook管理器对象。
    """
    manager = HookManager()

    manager.register(
        HookEvent.USER_PROMPT_SUBMIT,
        context_inject_hook,
    )

    manager.register(
        HookEvent.PRE_TOOL_USE,
        permission_hook,
    )

    manager.register(
        HookEvent.POST_TOOL_USE,
        large_output_hook,
    )

    manager.register(
        HookEvent.STOP,
        summary_hook,
    )

    return manager


# ═══════════════════════════════════════════════════════════
# 钩子系统 hook system
# ═══════════════════════════════════════════════════════════

# HOOK 事件定义
HOOK = {"UserPromptSubmit": [], "PreToolUse":[], "PostToolUse":[], "Stop":[]}


def register_hook(event: str, callback):
    """ 注册 hook 函数。

    注册一个 hook 函数到指定事件的回调列表中。
    
    Args:
        event (str): 事件名称，必须是 HOOK 中定义的事件。
        callback (callable): 要注册的 hook 函数，必须是可调用对象。
    
    Returns:
        None
    """
    HOOK[event].append(callback)


def trigger_hooks(event: str, *args):   # args 收集调用时传入的额外参数，打包成元组
    """ 触发 hook 函数。

    触发指定事件的所有注册 hook 函数，将额外参数传递给每个 hook 函数。
    
    Args:
        event (str): 事件名称，必须是 HOOK 中定义的事件。
        args (*args): 额外参数，将传递给每个 hook 函数。
    
    Returns:
        result: 第一个非 None 的结果。
        None: 如果事件名称不存在，返回 None。
    """
    # 触发所有注册的 hook 函数
    for callback in HOOK[event]:
        result = callback(*args)    # *args 把元组拆开，传给钩子回调的函数
        if result is not None:
            return result
    return None


register_hook("UserPromptSubmit", context_inject_hook)
register_hook("PreToolUse", permission_hook)
register_hook("PreToolUse", log_hook)
register_hook("PostToolUse", large_output_hook)
register_hook("Stop", summary_hook)
