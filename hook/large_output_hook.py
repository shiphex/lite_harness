""" 输出过大时发出警告。

    当输出字符串的长度超过 4096 个字符时，会打印警告信息。
    该 hook 函数用于在 PostToolUse 事件触发时检查输出字符串的长度。

    Typical usage example:
        import hook
        blocked = hook.trigger_hooks("PostToolUse", block)
"""

import config
from observability.logger import get_logger
logger = get_logger(__name__)


def large_output_hook(ctx, block, output: str):
    """ 输出过大时发出警告。

    检查输出字符串的长度是否超过 4096 个字符。
    如果超过 4096 个字符，会打印警告信息。
    
    Args:
        block (Block): 调用该 hook 函数的 Block 对象。
        output (str): 要检查的输出字符串。

    Returns:
        None
    """
    if len(output) > config.Config().get_content_length()["MAX_INLINE_TOOL_RESULT_TOKENS"]:
        logger.debug(
            f"[HOOK] {block.name} 输出过大，长度为 {len(output)}。"
        )
    return None
