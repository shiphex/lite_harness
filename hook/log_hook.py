""" 记录 hook 函数。 

该 hook 用于在每次工具调用时记录工具调用信息。

Typical usage example:
    import hook
    hook.trigger_hooks("PreToolUse", block, output)
"""

import cli
from observability.logger import get_logger
logger = get_logger(__name__)


def log_hook(ctx, block):
    """ 记录每次工具调用。

    PreToolUse：该 hook 用于在每次工具调用时记录工具调用信息。
    
    Args:
        block (Block): 调用的工具块。
    
    Returns:
        None
    """
    args_preview = str(list(block.input.values())[:2])[:60]
    logger.info(
        f"[HOOK] {block.name}({args_preview})"
    )
    return None