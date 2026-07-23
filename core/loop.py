""" Agent 的工作循环 Modules.

该循环负责调用模型接口，执行工具调用，保存模型输出。

Typical usage example:
    from core.loop import agent_loop
    agent_loop(messages)
"""

import cli
import api
import tools
import hook
import config


# skill 注册表
SKILL_REGISTRY: dict[str, dict] = {}

# 系统提示词


def agent_loop(messages: list):
    """ Agent 的工作循环 object.

    该循环负责调用模型接口，执行工具调用，保存模型输出。
    
    Args:
        messages: 包含用户输入和模型输出的消息列表。
    
    Returns:
        None

    Raises:
        None
    """

    while True:
        # 调用模型接口
        response = api.call_model(messages = messages,
                                  system_prompt = config.Config().get_system_prompt(),
                                  tools = tools.TOOLS_LIST)

        # 保存模型输出
        messages.append({"role": "assistant", "content": response.content})

        # 判断模型返回消息中是否有工具调用
        if response.stop_reason != "tool_use":
            # 触发 Stop hook
            force = hook.trigger_hooks("Stop", messages)
            if force:
                messages.append({"role": "user", "content": force})
            return

        # 初始化模型输出储存列表
        results = []
        # 判断本 block 是否为工具调用
        for block in response.content:
            if block.type != "tool_use":
                continue
            
            # 打印工具调用名称
            cli.put_agent_other_info(f"[TOOL]: {block.name}")

            # 在执行之前，触发 PreToolUse hook
            blocked = hook.trigger_hooks("PreToolUse", block)
            if blocked:
                # 返回并记录 PreToolUse hook 的结果
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(blocked)})
                continue

            # 执行工具调用
            output = tools.call_tool(block.name, block.input)

            # 触发 PostToolUse hook
            hook.trigger_hooks("PostToolUse", block, output)
            
            cli.put_agent_other_info(f"{output[:200]}")
            # 保存工具调用结果
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": output,
            })

        # 将调用工具的结果作为新消息追加，以供 model 调用（当没有使用压缩工具时）
        messages.append({"role": "user", "content": results})
        continue
