""" subagent 工具执行

该工具负责生成子智能体。

Typical usage example:
    spawn_subagent("生成一个子智能体，用于处理子问题。")

"""

from typing import List, Dict

import api
import cli
import config
import hook
import event
from . import tool_handler
from .tool_class import ToolContext
from builtin.memory import MemoryPolicy, MemoryMode
from event.sink import EventSink, NullEventSink
from event.interaction import Interaction, NonInteractiveInteraction


WORKDIR = config.Config().get_path_config("project_path")

# 设置子智能体系统提示词
SUB_SYSTEM = (f"你是一个编码助手，位于 {WORKDIR}，当前系统环境是 Windows。使用 PowerShell 解决任务。行动，无需解释。"
              "完成分配给你的任务，然后提交一份简明扼要的总结。"
              "不要再进一步委托子智能体。")


def extract_text(content) -> str:
    """ 从 messages content 块中提取文本。

    该函数负责从 messages content 块中提取文本内容。

    Args:
        content: 包含文本内容的消息块。

    Returns:
        text: 提取的文本内容。

    Raises:
        None
    """

    # 从 messages content 块中提取文本。
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content)

    texts = []
    for block in content:
        if isinstance(block, dict):
            if block.get("type") == "text":
                texts.append(str(block.get("text", "")))
        elif getattr(block, "type", "") == "text":
            texts.append(str(getattr(block, "text", "")))
        elif isinstance(block, str):
            texts.append(block)

    return "\n".join(text for text in texts if text)


def create_subagent_runtime(history: List, 
                            context: Dict,
                            events: EventSink,
                            interaction: Interaction,
                            ):
    """ 创建子智能体运行时。
    
    Args:
        history: 子智能体的历史记录。
        context: 子智能体的上下文。
        events: 子智能体的事件。
        interaction: 子智能体的交互。

    Returns:
        AgentRuntime: 子智能体的运行时环境。

    """
        # 配置 queryLoop 循环的 RunPolicy
    from core.runtime import RunPolicy, state, RuntimeFactory

    configured_model = dict(config.Config().get_model_config())
    fallback_model = dict(configured_model)
    fallback_model["model_name"] = (
        configured_model.get("fallback_model_name")
        or configured_model["model_name"]
    )
    content_config = config.Config().get_content_length()
    agent_RunPolicy = RunPolicy(max_turns = 30,
                                prompt = "你是一个子智能体 subagent，完成工作后请提交一份简明扼要的总结，标题为“[subagent result]”。",
                                model = configured_model,
                                fallback_model = fallback_model,
                                tools_list = tool_handler.STANDARD_TOOLS_LIST, 
                                tool_handler = tool_handler.STANDARD_TOOLS_HANDLERS,
                                can_ask_user = False)
            
    # 初始化 queryLoop 循环的运行状态
    agent_state = state(messages = history, 
                                context = context, 
                                max_output_tokens = content_config["MAIN_OUTPUT_TOKENS"],
                                toolUse_prompt = "",
                                turn_count = 0,
                                transition = "", 
                                max_output_tokens_override = False,
                                recovery_count = 0,
                                has_attempted_reactive_compact = False,
                                current_model = agent_RunPolicy.model,
                                consecutive_529 = 0 )

    # 通过随机数生成子智能体名称
    import random
    agent_name = f"Subagent_{random.randint(0, 1000000)}"
    memoryPolicy = MemoryPolicy(
        mode = MemoryMode.READ_ONLY,
        namespace = "subagent",
    )

    runtime = RuntimeFactory.create(
        agent_name = agent_name,
        policy = agent_RunPolicy,
        state = agent_state,
        memory_policy = memoryPolicy,
        workspace = config.Config().get_path_config("project_path"),
        session_id = None,
        events = events,
        interaction = interaction,
    )
    
    return runtime


def run_subagent(context: ToolContext, description: str) -> str:
    """ 运行子智能体。"""
    # 初始化历史记录
    from core.loop import query_loop

    history = []

    runtime = create_subagent_runtime(history, 
                                    {},
                                    events=NullEventSink(),
                                    interaction=NonInteractiveInteraction())
    
    # 告知用户系统信息
    runtime.events.emit(
        event.make_event(
                runtime,
                event.EventType.SYSTEM_MESSAGE,
                trigger=f"[Subagent] {runtime.agent_name} 任务: {description[:50]}",
            )
    )

    # 执行 UserPromptSubmit hook
    runtime.hooks.run(
        hook.HookEvent.USER_PROMPT_SUBMIT,
        hook.make_hook_context(runtime),
        description,
    )

    history.append({"role": "user", "content": description})

    agent_state, status = query_loop(runtime)

    # 更新上下文
    history = agent_state.messages

    # 如果在工具使用过程中达到安全限值，则采取回退措施
    result = extract_text(history[-1]["content"])
    if not result:
        for msg in reversed(history):  # 返回迭代器，从后往前遍历
            # 最后一条消息是 tool_result，请向后查找助手文本
            if msg["role"] == "assistant":
                result = extract_text(msg["content"])
                if result:
                    break

        if not result:
            result = "Subagent 在尝试 30 次后仍未给出最终答案而停止。"

    runtime.events.emit(
        event.make_event(
            runtime,
            event.EventType.SYSTEM_MESSAGE,
            trigger = f"[Subagent] {runtime.agent_name} 结果: {result}",
        )
    )

    # 仅提供摘要，完整消息历史记录已丢弃
    return result


def spawn_subagent(context: ToolContext, description: str) -> str:
    """ subagent 循环函数。(已废弃)

    subagent 的 loop 循环

    Args:
        description: 子智能体的描述。

    Returns:
        result: 子智能体输出的摘要。

    Raises:
        None
    """

    # 使用新 messages[] 生成子代理，仅返回摘要。
    cli.put_agent_other_info("\033[36m+++++ [Subagent spawned] +++++\033[0m")
    messages = [{"role": "user", "content": description}]

    # subagent 循环
    for _ in range(30):
        # 调用 model 回答问题，并获得 model 回答的文本内容
        response = api.call_model(messages = messages,
                                  system_prompt = SUB_SYSTEM,
                                  tools = tool_handler.STANDARD_TOOLS_LIST)
    
        # 将 model 回答的文本内容添加到历史记录
        messages.append({"role": "assistant", "content": response.content})

        # 若无工具调用，表示循环已经完成
        if response.stop_reason != "tool_use":
            break

        # 若有工具调用
        results = []
        for block in response.content:
            # 检测是否调用工具，若不是则跳过
            if block.type == "tool_use":
                # 在执行之前，触发 PreToolUse hook
                blocked = hook.trigger_hooks("PreToolUse", block)
                if blocked:
                    # 返回并记录 PreToolUse hook 的结果
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(blocked)})
                    continue
                
                # 获取返回的需调用工具的名字，再从 STANDARD_TOOLS_HANDLERS 中获取对应的函数指针
                handler = tool_handler.STANDARD_TOOLS_HANDLERS.get(block.name)
                # 将 block.input 的值作为参数传递给 handler 指向的函数，并返回函数执行结果   
                output = (
                    handler(context, **block.input)
                    if handler
                    else f"Unknown: {block.name}"
                )

                # 触发 PostToolUse hook
                hook.trigger_hooks("PostToolUse", block, output)

                # 输出 subagent 执行结果
                cli.put_agent_other_info(f"[sub] {block.name}:\n{str(output)[:100]}")

                # 记录工具调用结果
                results.append({"type": "tool_result", 
                                "tool_use_id": block.id, 
                                "content": output})

        # 将调用工具的结果作为新消息追加，以供 model 调用
        messages.append({"role": "user", "content": results})

    # 如果在工具使用过程中达到安全限值，则采取回退措施
    result = extract_text(messages[-1]["content"])
    if not result:
        for msg in reversed(messages):  # 返回迭代器，从后往前遍历
            # 最后一条消息是 tool_result，请向后查找助手文本
            if msg["role"] == "assistant":
                result = extract_text(msg["content"])
                if result:
                    break

        if not result:
            result = "Subagent 在尝试 30 次后仍未给出最终答案而停止。"

    cli.put_agent_other_info("----- [Subagent done] -----")

    # 仅提供摘要，完整消息历史记录已丢弃
    return result
