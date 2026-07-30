""" Agent 的顶层入口 Modules.

该顶层入口 Modules 告知用户系统信息，获取用户输入，执行 UserPromptSubmit hook，
执行 agent loop 工作循环（模型输出由 agent loop 工作循环处理），执行系统输出。

Typical usage example:
    import core.agent as agent
    agent()
"""

import cli
import hook
import builtin
from .loop import agent_loop



def agent():
    """ Agent 的顶层入口 object.

    该顶层入口 object 告知用户系统信息，获取用户输入，执行 UserPromptSubmit hook，
    执行 agent loop 工作循环（模型输出由 agent loop 工作循环处理），执行系统输出。

    Args:
        None

    Returns:
        None
        
    Raises:
        None
    """
    # 告知用户系统信息
    cli.inform_system_info("输入问题，回车发送。输入 q 退出。")
    
    # 初始化历史记录
    history = []
    # 初始化上下文
    context = builtin.update_context({}, [])
    while True:
        # 获取用户输入
        try:
            user_input = cli.get_user_input()
        except (EOFError, KeyboardInterrupt):
            break
        if user_input.strip().lower() in ("q", "exit", " "):
            break
        
        # 执行 UserPromptSubmit hook
        hook.trigger_hooks("UserPromptSubmit", user_input)


        # 记录用户输入
        history.append({"role": "user", "content": user_input})

        # 执行 agent_loop 工作循环
        agent_loop(history, context)

        # 更新上下文
        context = builtin.update_context(context, history)

        # 执行系统输出
        response = history[-1]["content"]
        if isinstance(response, list):
            for block in response:
                if getattr(block, "type", None) == "text":
                    # 执行系统输出
                    cli.put_agent_output(block.text)

        