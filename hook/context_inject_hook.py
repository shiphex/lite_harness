""" context 注入 hook. 

    UserPromptSubmit：在用户输入到达 LLM 之前记录用户输入，用于上下文注入。

    Typical usage example:
        import hook
        hook.trigger_hooks("UserPromptSubmit", query)
"""

import config
from observability.logger import get_logger
logger = get_logger(__name__)


def context_inject_hook(ctx, query: str):
    """  上下文注入 hook 函数。

    UserPromptSubmit：记录用户输入，用于上下文注入。

    Args:
        query (str): 用户输入的查询字符串。
    
    """
    WORKDIR = config.Config().get_path_config("project_path")
    logger.debug(
        f"[HOOK] UserPromptSubmit: {query}, working in {WORKDIR}"
    )
    return None