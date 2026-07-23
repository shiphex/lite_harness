""" context 注入 hook. 

    UserPromptSubmit：在用户输入到达 LLM 之前记录用户输入，用于上下文注入。

    Typical usage example:
        import hook
        hook.trigger_hooks("UserPromptSubmit", query)
"""

import config
import cli

def context_inject_hook(query: str):
    """  上下文注入 hook 函数。

    UserPromptSubmit：记录用户输入，用于上下文注入。

    Args:
        query (str): 用户输入的查询字符串。
    
    """
    WORKDIR = config.Config().get_path_config("project_path")
    cli.put_agent_other_info(f"[HOOK] UserPromptSubmit: working in {WORKDIR}")
    return None