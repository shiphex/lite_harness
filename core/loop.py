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
import builtin


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

    # 加载需要注入本轮会话的记忆内容
    memories_content = builtin.load_memories(messages)
    memories_turn = len(messages) - 1 if messages and isinstance(messages[-1].get("content"), str) else None
    system = builtin.build_system()

    while True:

        # 执行压缩管线前保存快照以便准确提取储存的记忆
        pre_compress = [m if isinstance(m, dict) else
                        {"role": m.get("role", ""), "content": m.get("content", "")}
                        for m in messages]

        # 执行压缩管线
        messages[:] = tools.tool_result_budget(messages)      # L3 储存大的工具调用输出结果
        messages[:] = tools.snip_compact(messages)            # L1 裁剪式压缩
        messages[:] = tools.micro_compact(messages)           # L2旧工具输出结果占位符替换
        # 若压缩后历史记录超过上下文大小，执行紧凑式压缩
        CONTEXT_LIMIT = 50000
        if tools.estimate_size(messages) > CONTEXT_LIMIT:
            print("[auto compact]")
            messages[:] = tools.compact_history(messages)

        try:
            # 构建请求消息
            request_messages = messages
            if memories_content and memories_turn is not None and memories_turn < len(messages):
                request_messages = messages.copy()
                # --- 在 request_messages[memories_turn] = {} 上方加入安全的提取逻辑 ---
                raw_content = messages[memories_turn]["content"]
                extracted_texts = []
                if isinstance(raw_content, list):
                    for block in raw_content:
                        # 1. 兼容标准字典格式: {"type": "text", "text": "..."}
                        if isinstance(block, dict) and "text" in block:
                            extracted_texts.append(block["text"])
                        # 2. 兼容 Anthropic / LangChain 的 TextBlock 对象 (有 text 属性)
                        elif hasattr(block, "text"):
                            extracted_texts.append(block.text)
                        # 3. 如果列表中意外混入了普通字符串，直接添加
                        elif isinstance(block, str):
                            extracted_texts.append(block)
                        # 4. 如果是 ToolUseBlock 或者是其他工具块，则不提取（直接忽略）

                    # 用换行或空格将提取出来的文本块合并
                    current_message_text = "\n".join(extracted_texts)
                else:
                    # 如果不是列表，本身就是普通字符串，直接强转
                    current_message_text = str(raw_content)
                # --- 安全的提取逻辑结束 ---
                request_messages[memories_turn] = {
                    **request_messages[memories_turn],
                    "content": memories_content + "\n\n" + current_message_text,
                }

            # 调用 model 回答问题，并获得 model 回答的文本内容
            response = api.call_model(messages = request_messages,
                                      system_prompt = system,
                                      tools = tools.TOOLS_LIST)
            reactive_retries = 0
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
            # 从压缩前的的快照中提取记忆
            builtin.extract_memories(pre_compress)
            builtin.consolidate_memories()

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

            # 对调用了压缩工具进行处理
            if block.name == "compact":
                messages[:] = tools.compact_history(messages)
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": "[已压缩： 对话历史已生成摘要。]",
                })
                messages.append({"role": "user", "content": results})
                break   # 使用压缩工具后直接 break，不使用 for……else 语句中 else 后的 messages.append(results)


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
        else:
            # 将调用工具的结果作为新消息追加，以供 model 调用（当没有使用压缩工具时）
            messages.append({"role": "user", "content": results})
            continue

        # 让使用压缩工具后的 break 到达这里得到处理
        continue 
