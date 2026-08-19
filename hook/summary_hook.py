""" 打印摘要的 hook 函数。

    循环即将结束时打印摘要。
    打印当前会话使用的工具调用次数。

    Typical usage example:
        import hook
        force = trigger_hooks("Stop", messages)
"""

from observability.logger import get_logger
logger = get_logger(__name__)


def summary_hook(ctx, message: list):
    """ 打印摘要的 hook 函数。

    循环即将结束时打印摘要。
    打印当前会话使用的工具调用次数。

    Args:
        message (list): 包含所有消息的列表。
    
    Returns:
        None
    """
    tool_count = sum(1 for m in message 
                     for b in (m.get("content") if isinstance(m.get("content"), list) else [])
                     if isinstance(b, dict) and b.get("type") == "tool_result")
    logger.debug(
        f"[HOOK] Stop: session used {tool_count} tool calls."
        )
    return None