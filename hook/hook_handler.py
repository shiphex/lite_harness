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
