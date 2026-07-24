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


# 反应式紧凑的重试次数限制
MAX_REACTIVE_RETRIES = 1  


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

    reactive_retries = 0

    while True:

        # 执行压缩管线
        messages[:] = tools.tool_result_budget(messages)      # L3 储存大的工具调用输出结果
        messages[:] = tools.snip_compact(messages)            # L1 裁剪式压缩
        messages[:] = tools.micro_compact(messages)           # L2旧工具输出结果占位符替换

        try:
            # 调用 model 回答问题，并获得 model 回答的文本内容
            response = api.call_model(messages = messages,
                                      system_prompt = config.Config().get_system_prompt(),
                                      tools = tools.TOOLS_LIST)
        except Exception as e:
            if ("prompt is too long" in str(e).lower() \
                or "too many tokens" in str(e).lower() \
                or "exceeds the available context size" in str(e).lower()) \
                and reactive_retries < MAX_REACTIVE_RETRIES:
                cli.inform_system_warning("\n[WARN] [重新执行压缩]")
                messages[:] = tools.compact_history(messages)
                reactive_retries += 1
                continue
            raise   # 抛出异常，结束循环

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

            # 对调用了压缩工具进行处理
            if block.name == "compact":
                messages[:] = tools.compact_history(messages)
                messages.append({
                    "role": "user",
                    "content": "[压缩工具已执行完成] 请基于上面的摘要继续当前任务；不要因为本条消息再次调用 compact。",
                })
                break   # 使用压缩工具后直接 break，不使用 for……else 语句中 else 后的 messages.append(results)


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
        else:
            # 将调用工具的结果作为新消息追加，以供 model 调用（当没有使用压缩工具时）
            messages.append({"role": "user", "content": results})
            continue

        # 让使用压缩工具后的 break 到达这里得到处理
        continue 
