""" Agent 的顶层入口 Modules.

该顶层入口 Modules 告知用户系统信息，获取用户输入，执行 UserPromptSubmit hook，
执行 agent loop 工作循环（模型输出由 agent loop 工作循环处理），执行系统输出。

Typical usage example:
    import core.agent as agent
    agent()
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict

import cli
import hook
import builtin
import tools
import config
from .loop import query_loop
from .runtime import RunPolicy, state, RuntimeFactory
from builtin.memory import MemoryPolicy, MemoryMode



def create_master_runtime(history: List, context: Dict):
    """ 创建主 Agent 的运行时环境。

    Args:
        None

    Returns:
        AgentRuntime: 主 Agent 的运行时环境。
    """
        # 配置 queryLoop 循环的 RunPolicy
    configured_model = dict(config.Config().get_model_config())
    fallback_model = dict(configured_model)
    fallback_model["model_name"] = (
        configured_model.get("fallback_model_name")
        or configured_model["model_name"]
    )
    content_config = config.Config().get_content_length()
    agent_RunPolicy = RunPolicy(max_turns = 300,
                                prompt = "",
                                model = configured_model,
                                fallback_model = fallback_model,
                                tools_list = tools.TOOLS_LIST, 
                                tool_handler = tools.TOOLS_HANDLERS,
                                can_ask_user = True)
            
    # 初始化 queryLoop 循环的运行状态
    agent_state = state(messages = history, 
                                context = context, 
                                max_output_tokens = content_config["MAIN_OUTPUT_TOKENS"],
                                toolUse_prompt = "",
                                turn_count = 0,
                                transition = "", 
                                max_output_tokens_override = False,
                                recovery_count = 3, 
                                has_attempted_reactive_compact = False,
                                current_model = agent_RunPolicy.model,
                                consecutive_529 = 0 )

    memoryPolicy = MemoryPolicy(
        mode = MemoryMode.READ_WRITE,
        namespace = "master",
    )

    runtime = RuntimeFactory.create(
        agent_name = "Master Agent",
        policy = agent_RunPolicy,
        state = agent_state,
        memory_policy = memoryPolicy,
        workspace = config.Config().get_path_config("project_path"),
        session_id = None,
    )
    
    return runtime

def master_agent():
    """ 主 Agent 的顶层入口 object.

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

    runtime = create_master_runtime(history, context)

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
        runtime.state.turn_count = 0
        agent_state, status = query_loop(runtime)

        # 更新上下文
        history = agent_state.messages
        context = builtin.update_context(context, history, memory_index=runtime.memory.index_path)

        # 执行系统输出
        response = next(
            (
                message.get("content")
                for message in reversed(history)
                if message.get("role") == "assistant"
            ),
            "",
        )
        if isinstance(response, list):
            for block in response:
                block_type = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
                if block_type == "text":
                    # 执行系统输出
                    text = block.get("text", "") if isinstance(block, dict) else block.text
                    cli.put_agent_output(text)
                    cli.put_agent_other_info(f"当前状态：{status}")


def agent():
    """ 旧版 Agent 的顶层入口 object.

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
        # agent_loop(history, context)

        # 更新上下文
        context = builtin.update_context(context, history)

        # 执行系统输出
        response = history[-1]["content"]
        if isinstance(response, list):
            for block in response:
                block_type = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
                if block_type == "text":
                    # 执行系统输出
                    text = block.get("text", "") if isinstance(block, dict) else block.text
                    cli.put_agent_output(text)
