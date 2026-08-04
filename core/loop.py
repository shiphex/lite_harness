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

from api.anthropic_adapter import AnthropicAdapter
from api.contract import ModelRequest



def compact_pipeline(messages: list):
    """ 执行压缩管线，压缩会话历史记录。

    Args:
        messages (list): 包含当前会话历史记录的列表。
    
    Returns:
        pre_compress: 压缩前的会话历史记录快照。
        messages: 压缩后的会话历史记录列表。
    """
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

    return pre_compress, messages


def struct_massages(messages: list, memories_content: str):
    """ 结构化会话历史记录，将记忆内容插入到最新消息中。

    Args:
        messages (list): 包含当前会话历史记录的列表。
        memories_content (str): 要插入的最新消息中的记忆内容。
    
    Returns:
        request_messages: 更新后的会话历史记录列表，包含记忆内容的最新消息。
    """

    memories_turn = len(messages) - 1 if messages and isinstance(messages[-1].get("content"), str) else None
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

    return request_messages


def execute_tool(block: dict, messages: list):
    """ 执行工具调用。

    Args:
        block (dict): 包含工具调用信息的字典。
        messages (list): 包含当前会话历史记录的列表。
    
    Returns:
        list: 更新后的会话历史记录列表，包含工具调用结果。
    """

    # 7. 执行工具调用

    # 初始化模型输出储存列表
    results = []

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
        return messages

    # 在执行之前，触发 PreToolUse hook
    blocked = hook.trigger_hooks("PreToolUse", block)
    if blocked:
        # 返回并记录 PreToolUse hook 的结果
        results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(blocked)})
        messages.append({"role": "user", "content": results})
        return messages
    
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
    messages.append({"role": "user", "content": results})
    return messages
    



def query_loop(RunPolicy: dict, state: dict):
    """ queryLoop 循环 object.

    该循环负责调用模型接口，执行工具调用，保存模型输出。
    该循环为全部种类的 Agent 提供统一的工作流程。
    通过 RunPolicy 来配置不同 Agent 的工作流程。

    Args:
        RunPolicy: 包含不同 Agent 工作流程的字典。
        state: 包含当前会话状态的字典。 
    
    Returns:
        None

    Raises:
        None
    """
    
    #1. 记忆提取
    # 加载需要注入本轮会话的记忆内容
    messages = state["messages"]
    context = RunPolicy["context"]# LLM 状态加载
    memories_content = builtin.load_memories(messages)
    

    #2. 配置加载（提示词加载、模型加载）  
    # 初始化系统提示词
    system = builtin.get_system_prompt(context)
    
    while True:
        # 1. 解析状态参数(state)
        # 2. 执行压缩管线
        pre_compress, messages = compact_pipeline(messages)
        
        # 3. 规范化请求消息构建
        request_messages = struct_massages(messages, memories_content)

        # 4. 调用 LLM
        try: 
            adapter = AnthropicAdapter.from_model_config({
                "model_url": "http://localhost:8000",
                "api_key": "no-key",
            })
            request = ModelRequest(
                model = state["current_model"]("model_name"),
                tools = tools.TOOLS_LIST,
                system_prompt = system,
                messages = request_messages,
                max_tokens = state["max_output_tokens"],
            )
            response = builtin.with_llm_retry(adapter.complete(request), state, RunPolicy)
        # 5. 错误恢复
        except Exception as e:
            if builtin.is_prompt_too_long_error(e):
                if not state["has_attempted_reactive_compact"]:
                    print("\033[33m\n⚠ [重新执行压缩]\033[0m")
                    messages[:] = tools.reactive_compact(messages)
                    state["has_attempted_reactive_compact"] = True
                    continue                # Continue Site 2: Prompt Too Long
                print("  \033[31m[unrecoverable] 压缩后依然过长。\033[0m")
                messages.append({"role": "assistant", "content": [
                    {"type": "text",
                     "text": "[Error] 上下文过大，无法继续。"}]})
                state["messages"] = messages
                return state, {"reason": "prompt_too_long"}

        # 若 model 回答的文本内容超过上下文大小，执行 output_tokens_too_long_error 函数
        if response.stop_reason == "max_tokens":
            state, messages = builtin.output_tokens_too_long_error(messages, state)
            if state["recovery_count"] >= builtin.MAX_RECOVERY_RETRIES:
                state["messages"] = messages
                return state, {"reason": "prompt_too_long"}
            if state["max_output_tokens_override"] and state["recovery_count"] < builtin.MAX_RECOVERY_RETRIES:
                state["max_output_tokens"] = int(state["max_output_tokens"] * 2)
                continue            # Continue Site 3: Max Output Tokens
            continue

        # 保存模型输出
        messages.append({"role": "assistant", "content": response.content})

        # 8. Stop Hook → 终止或继续
        # 判断模型返回消息中是否有工具调用
        if response.stop_reason != "tool_use":
            # 从压缩前的的快照中提取记忆
            builtin.extract_memories(pre_compress)
            builtin.consolidate_memories()
    
            # 触发 Stop hook
            force = hook.trigger_hooks("Stop", messages)
            if force:
                messages.append({"role": "user", "content": force})
                state["messages"] = messages
                return state, {"reason": "completed"}          # return Terminal — 唯一的退出点

        # 6. 收集 tool_use 块
        for block in response.content:
            if block.type != "tool_use":
                continue                    # Continue Site 7: Tool Execution
            # 7. 执行工具调用
            messages = execute_tool(block, messages)
            
        # 更新上下文
        context = builtin.update_context(context, messages)
        system = builtin.get_system_prompt(context)

        
        # 9. 更新状态 → continue



# 反应式紧凑的重试次数限制
MAX_REACTIVE_RETRIES = 1  

def agent_loop(messages: list, context: dict):
    """ Agent 的工作循环 object.

    该循环负责调用模型接口，执行工具调用，保存模型输出。
    
    Args:
        messages: 包含用户输入和模型输出的消息列表。
        context: 包含当前会话上下文的字典。
    
    Returns:
        None

    Raises:
        None
    """

    # 加载需要注入本轮会话的记忆内容
    memories_content = builtin.load_memories(messages)
    memories_turn = len(messages) - 1 if messages and isinstance(messages[-1].get("content"), str) else None

    # 初始化系统提示词
    system = builtin.get_system_prompt(context)

    # LLM 状态加载
    state = builtin.RecoveryState()

    # 模型模式
    model_pattern = "default"

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
            response = builtin.with_retry( 
                lambda mp = model_pattern, mdl = {"model_name": state.current_model}:
                api.call_model(messages = request_messages,
                               system_prompt = system,
                               tools = tools.TOOLS_LIST, 
                               model_pattern = mp, 
                               model_config = mdl), 
                state)
            
        except Exception as e:
            if builtin.is_prompt_too_long_error(e):
                if not state.has_attempted_reactive_compact:
                    print("\033[33m\n⚠ [重新执行压缩]\033[0m")
                    messages[:] = tools.reactive_compact(messages)
                    state.has_attempted_reactive_compact = True
                    continue
                print("  \033[31m[unrecoverable] 压缩后依然过长。\033[0m")
                messages.append({"role": "assistant", "content": [
                    {"type": "text",
                     "text": "[Error] 上下文过大，无法继续。"}]})
                return

        # 若 model 回答的文本内容超过上下文大小，执行 max_tokens_too_long_error 函数
        if response.stop_reason == "max_tokens":
            state, messages = builtin.max_tokens_too_long_error(messages, state)
            if state.recovery_count >= builtin.MAX_RECOVERY_RETRIES:
                return
            if state.has_escalated and state.recovery_count < builtin.MAX_RECOVERY_RETRIES:
                model_pattern = "long"
                continue
            continue

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

            # 更新上下文
            context = builtin.update_context(context, messages)
            system = builtin.get_system_prompt(context)
            continue

        # 让使用压缩工具后的 break 到达这里得到处理
        continue 
