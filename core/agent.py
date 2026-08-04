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
from .loop import agent_loop
from .loop import query_loop


@dataclass(frozen=True)
class RunPolicy():
    """ 用于配置 queryLoop 循环的参数

    所有的 Agent 共用的通用 queryLoop 循环结构，
    通过配置 queryLoop 的 RunPolicy 中参数的不同
    得到不同种类的 Agent，该参数在循环中不改变。

    参数包括：
    - max_turns: 最大循环次数
    - prompt: 系统提示词、用户提示词（静态提示词）
    - Model: 调用的模型
    - fallbackModel: 失败时调用的模型
    - CanUseTool: 可以使用的工具的列表
    - CanAskUser: 是否可以询问用户问题
    - Context: 上下文参数，用于存储会话中的记忆、系统状态等信息
    """
    max_turns: int = 300
    prompt: str = ""
    model: Dict = field(default_factory=dict)
    fallback_model: Dict = field(default_factory=dict)
    tools_list: List = field(default_factory=list)
    can_ask_user: bool = False
    context: Dict = field(default_factory=dict)


@dataclass()
class state():
    """ 用于记录 queryLoop 循环的运行状态，该参数在循环中会改变。

    一个 Agent 的运行状态通过 state 中的参数进行记录，
    这些参数随着 queryLoop 循环的进行而改变。

    参数包括：
    - messages: 对话消息列表
    - maxOutputTokens: 最大输出token数
    - toolUsePrompt: 工具调用提示词（动态提示词）
    - turnCount: 当前循环次数计数
    - transition: 上次循环迭代的原因
    - max_output_tokens_override: 是否覆盖最大输出token数
    - recovery_count: 最大输出token数恢复次数
    """
    messages: List = field(default_factory=list)
    max_output_tokens: int = 4096
    toolUse_prompt: str = ""
    turn_count: int = 0
    transition: str = ""
    max_output_tokens_override: bool = False
    recovery_count: int = 3
    has_attempted_reactive_compact: bool = False
    current_model: Dict = field(default_factory=dict)
    consecutive_529: int = 0


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

        # 配置 queryLoop 循环的 RunPolicy
        agent_RunPolicy = asdict(RunPolicy(max_turns = 300, 
                                    prompt = "", 
                                    model = {"API": "Anthropic", 
                                            "model_url": "http://localhost:8000", 
                                            "api_key": "no-key", 
                                            "model_name": "Qwen3.5"},
                                    fallback_model = {"API": "Anthropic", 
                                         "model_url": "http://localhost:8000", 
                                         "api_key": "no-key", 
                                         "model_name": "Qwen3.5_4B"},
                                    tools_list = tools.TOOLS_LIST, 
                                    can_ask_user = True, 
                                    context = context))
        
        # 初始化 queryLoop 循环的运行状态
        agent_state = asdict(state(messages = history, 
                            max_output_tokens = 4096,
                            toolUse_prompt = "",
                            turn_count = 0,
                            transition = "", 
                            max_output_tokens_override = False,
                            recovery_count = 3, 
                            has_attempted_reactive_compact = False,
                            current_model = agent_RunPolicy["model"],
                            consecutive_529 = 0 ))

        # 执行 agent_loop 工作循环
        agent_state, status = query_loop(agent_RunPolicy, agent_state)

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
        agent_loop(history, context)

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
