""" Agent 的工作循环 Modules.

该循环负责调用模型接口，执行工具调用，保存模型输出。

Typical usage example:
    from core.loop import agent_loop
    agent_loop(messages)
"""


import event
import tools
import hook
import builtin
import config

from api.adapter_factory import create_adapter
from api.contract import ModelRequest, ModelResponse
from .runtime import AgentRuntime
from event.interaction import ApprovalRequest
from tools.tool_class import ToolContext

from typing import Any

content_config = config.Config().get_content_length()


def compact_pipeline(runtime: AgentRuntime):
    """ 执行压缩管线，压缩会话历史记录。

    Args:
        messages (list): 包含当前会话历史记录的列表。
    
    Returns:
        pre_compress: 压缩前的会话历史记录快照。
        messages: 压缩后的会话历史记录列表。
    """

    messages = runtime.state.messages
    
    # 执行压缩管线前保存快照以便准确提取储存的记忆
    pre_compress = [m if isinstance(m, dict) else
                    {"role": m.get("role", ""), "content": m.get("content", "")}
                    for m in messages]

    runtime.events.emit(
                        event.make_event(
                            runtime,
                            event.EventType.COMPACT_STARTED,
                            trigger="auto start compact.",
                        )
                    )

    # 执行压缩管线
    messages[:] = tools.tool_result_budget(             # L3 储存大的工具调用输出结果
        messages = messages,
        artifacts = runtime.artifacts,
    )      
    messages[:] = tools.snip_compact(messages)          # L1 裁剪式压缩
    messages[:] = tools.micro_compact(messages)         # L2旧工具输出结果占位符替换
    # 若压缩后历史记录超过上下文大小，执行紧凑式压缩
    CONTEXT_LIMIT = 50000
    if tools.estimate_size(messages) > CONTEXT_LIMIT:
        messages[:] = tools.compact_history(messages, runtime.artifacts)

    runtime.events.emit(
                        event.make_event(
                            runtime,
                             event.EventType.COMPACT_COMPLETED,
                            trigger="auto complete compact.",
                        )
                    )

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


def _blocked_tool_result(
    runtime: AgentRuntime,
    block,
    reason: str,
) -> dict[str, Any]:
    """ 重整工具调用结果，记录被阻塞的工具调用。

    Args:
        runtime (AgentRuntime): 运行时环境。
        block (ToolUseBlock): 被阻塞的工具调用块。
        reason (str): 阻塞原因。
    
    Returns:
        dict[str, Any]: 包含被阻塞工具调用结果的字典。"""

    # 记录工具调用被阻塞事件
    runtime.events.emit(
        event.make_event(
            runtime,
            event.EventType.TOOL_BLOCKED,
            tool_call_id=block.id,
            tool_name=block.name,
            reason=reason,
        )
    )

    return {
        "type": "tool_result",
        "tool_use_id": block.id,
        "content": reason,
    }


def _handle_pre_tool_hook_result(
    runtime: AgentRuntime,
    block,
    hook_result: hook.HookResult,
) -> dict[str, Any] | None:
    """ 处理 PreToolUse hook 结果。

    处理拒绝的工具请求、需询问用户以决定的工具请求。
    
    Args:
        runtime (AgentRuntime): 运行时环境。
        block (ToolUseBlock): 被调用的工具调用块。
        hook_result (hook.HookResult): PreToolUse hook 结果。
    
    Returns:
        dict[str, Any] | None: 包含工具调用结果的字典，或 None。
    """
    match hook_result.action:
        case hook.HookAction.CONTINUE:
            return None

        case hook.HookAction.BLOCK:
            # 记录工具调用被阻塞事件
            reason = hook_result.message or "Tool use blocked by hook."
            return _blocked_tool_result(
                runtime,
                block,
                reason,
            )

        case hook.HookAction.ASK:
            if not runtime.policy.can_ask_user:
                return _blocked_tool_result(
                    runtime,
                    block,
                    "当前 Agent 不允许请求用户审批",
                )

            request = ApprovalRequest(
                tool_call_id=block.id,
                tool_name=block.name,
                arguments=block.input,
                reason=(
                    hook_result.message
                    or "该操作需要用户批准"
                ),
            )
        
            runtime.events.emit(
                event.make_event(
                    runtime,
                    event.EventType.APPROVAL_REQUESTED,
                    tool_call_id=request.tool_call_id,
                    tool_name=request.tool_name,
                    arguments=request.arguments,
                    reason=request.reason,
                )
            )
        
            approval = (
                runtime.interaction
                .request_approval(request)
            )
        
            runtime.events.emit(
                event.make_event(
                    runtime,
                    event.EventType.APPROVAL_RESOLVED,
                    tool_call_id=block.id,
                    tool_name=block.name,
                    approved=approval.approved,
                    message=approval.message,
                )
            )

            if approval.approved:
                return None

            reason = approval.message or "权限已被用户拒绝"
            return _blocked_tool_result(
                runtime,
                block,
                reason,
            )

        case _:
            raise ValueError(
                f"Unsupported HookAction: {hook_result.action!r}"
            )


def execute_tool(response: ModelResponse, runtime: AgentRuntime):
    """ 执行工具调用。

    Args:
        response (ModelResponse): 包含工具调用信息的响应。
    
    Returns:
        list: 更新后的会话历史记录列表，包含工具调用结果。
    """
    messages = runtime.state.messages

    # 初始化模型输出储存列表
    results = []
    status = "complete"
    # 6. 收集 tool_use 块
    for block in response.content:
        if block.type != "tool_use":
            continue                    # Continue Site 7: Tool Execution

        # 7. 执行工具调用
        # 记录工具调用事件
        runtime.events.emit(
            event.make_event(
                runtime,
                event.EventType.TOOL_REQUESTED,
                tool_call_id=block.id,
                tool_name=block.name,
                arguments=block.input,
            )
        )

        # 对调用了压缩工具进行处理
            # `compact` 是一个内部控制操作，而不是一个普通的执行工具。
            # 它会有意绕过 PreToolUse/PostToolUse 和 ToolExecutor。
        if block.name == "compact":
            runtime.events.emit(
                event.make_event(
                    runtime,
                    event.EventType.COMPACT_STARTED,
                    trigger="use compact tool.",
                )
            )

            messages[:] = tools.compact_history(messages, runtime.artifacts,)
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": "[已压缩： 对话历史已生成摘要。]",
            })

            runtime.events.emit(
                event.make_event(
                    runtime,
                    event.EventType.COMPACT_COMPLETED,
                    trigger="complete compact tool.",
                )
            )

            status = "compact"
            return results, status

        # 在执行之前，触发 PreToolUse hook
        hook_ctx = hook.make_hook_context(runtime)
        hook_result = runtime.hooks.run(hook.HookEvent.PRE_TOOL_USE,
                                        hook_ctx,
                                        block,
                                        )

        # 工具执行前询问用户是否执行
        terminal_result = _handle_pre_tool_hook_result(
            runtime,
            block,
            hook_result,
        )

        if terminal_result is not None:
            results.append(terminal_result)
            continue

        # 记录工具调用开始事件
        runtime.events.emit(
            event.make_event(
                runtime,
                event.EventType.TOOL_STARTED,
                tool_call_id=block.id,
                tool_name=block.name,
                arguments=block.input,
            )
        )

        # 执行工具调用
        output = runtime.tools.execute(context = ToolContext(runtime), 
                                       name = block.name, 
                                       args = block.input)

        # 触发 PostToolUse hook
        runtime.hooks.run(hook.HookEvent.POST_TOOL_USE,
                          hook_ctx,
                          block,
                          output,
        )

        # 记录工具调用完成事件
        runtime.events.emit(
            event.make_event(
                runtime,
                event.EventType.TOOL_COMPLETED,
                tool_call_id=block.id,
                tool_name=block.name,
                output=output,
            )
        )
        # 保存工具调用结果
        results.append({
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": output,
        })
        
    status = "complete"
    return results, status


def query_loop(runtime: AgentRuntime):
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

    runtime.events.emit(
        event.make_event(
            runtime,
            event.EventType.RUN_STARTED,
        )
    )
    
    # 0. 解析权限、状态参数
    state = runtime.state
    RunPolicy = runtime.policy

    messages = state.messages
    context = state.context
    max_turns = RunPolicy.max_turns
    tool_defs = RunPolicy.tools_list

    # 1. 记忆提取、提示词加载
    memories_content = runtime.memory.load(runtime, messages)

    while True:
        if max_turns > 0:
            if max_turns > 0 and state.turn_count >= max_turns:
                state.messages = messages
                runtime.events.emit(
                    event.make_event(
                        runtime,
                        event.EventType.RUN_COMPLETED,
                        trigger=f"max_turns {max_turns} reached",
                    )
                )
                return state, {"reason": "max_turns"}
            state.turn_count = state.turn_count + 1
            runtime.events.emit(
                event.make_event(
                    runtime,
                    event.EventType.TURN_STARTED,
                    trigger=f"turn {state.turn_count} started",
                )
            )

        system = runtime.prompt.build(runtime)
        context = state.context

        # 2. 执行压缩管线
        state.messages = messages
        state.context = context
        runtime.state = state
        pre_compress, messages = compact_pipeline(runtime)
        
        # 3. 规范化请求消息构建
        request_messages = struct_massages(messages, memories_content)

        # 4. 调用 LLM
        try: 
            response = builtin.with_llm_retry(
                lambda: create_adapter(state.current_model).complete(
                    ModelRequest(
                        model = state.current_model["model_name"],
                        tools = tool_defs,
                        system_prompt = system,
                        messages = request_messages,
                        max_tokens = state.max_output_tokens,
                    )
                ),
                state,
                RunPolicy,
            )
        # 5. 错误恢复
        except Exception as e:
            if builtin.is_prompt_too_long_error(e):
                if not state.has_attempted_reactive_compact:
                    runtime.events.emit(
                         event.make_event(
                            runtime,
                            event.EventType.COMPACT_STARTED,
                            trigger="prompt_too_long",
                        )
                    )
                    messages[:] = tools.reactive_compact(messages, runtime.artifacts)
                    state.has_attempted_reactive_compact = True
                    runtime.events.emit(
                        event.make_event(
                            runtime,
                            event.EventType.COMPACT_COMPLETED,
                            trigger="complete compact.",
                        )
                    )
                    continue                # Continue Site 2: Prompt Too Long
                runtime.events.emit(
                     event.make_event(
                        runtime,
                        event.EventType.ERROR,
                        code="prompt_too_long",
                        message="上下文过大，压缩后依然无法继续。",
                        recoverable=False,
                    )
                )
                messages.append({"role": "assistant", "content": [
                    {"type": "text",
                     "text": "[Error] 上下文过大，无法继续。"}]})
                state.messages = messages
                state.context = context
                runtime.events.emit(
                    event.make_event(
                        runtime,
                        event.EventType.RUN_COMPLETED,
                        trigger="prompt_too_long",
                    )
                )
                return state, {"reason": "prompt_too_long"}
            raise

        # 若 model 回答的文本内容超过上下文大小，执行 output_tokens_too_long_error 函数
        if response.stop_reason == "max_tokens":
            state, messages = builtin.output_tokens_too_long_error(messages, state)
            if state.recovery_count >= builtin.MAX_RECOVERY_RETRIES:
                state.messages = messages
                state.context = context
                runtime.events.emit(
                    event.make_event(
                        runtime,
                        event.EventType.RUN_COMPLETED,
                        trigger="prompt_too_long",
                    )
                )
                return state, {"reason": "prompt_too_long"}
            if state.max_output_tokens_override and state.recovery_count < builtin.MAX_RECOVERY_RETRIES:
                state.max_output_tokens = content_config["ESCALATED_MAX_OUTPUT_TOKENS"]
                continue            # Continue Site 3: Max Output Tokens
            continue

        # 保存模型输出
        messages.append({
            "role": "assistant",
            "content": response.message_blocks(),
        })

        # 8. Stop Hook → 终止或继续
        # 判断模型返回消息中是否有工具调用
        if response.stop_reason != "tool_use":
            # 从压缩前的的快照中提取记忆
            runtime.memory.extract(runtime, pre_compress)
            runtime.memory.consolidate(runtime)
    
            # 触发 Stop hook
            hook_ctx = hook.make_hook_context(runtime)
            force = runtime.hooks.run(hook.HookEvent.STOP,
                                      hook_ctx, 
                                      messages,
                    )
            if force.blocked:
                messages.append({"role": "user", "content": force.message})
                continue
            
            state.messages = messages
            state.context = context
            runtime.events.emit(
                event.make_event(
                    runtime,
                    event.EventType.RUN_COMPLETED,
                    trigger="run completed",
                )
            )
            return state, {"reason": "completed"}               # return Terminal — 唯一的退出点

        # 6. 收集 tool_use 块
        # 7. 执行工具调用
        state.messages = messages
        state.context = context
        runtime.state = state
        results, status = execute_tool(response, runtime)
        if status == "compact":
            continue
        else:
            messages.append({"role": "user", "content": results})
            
        # 更新上下文

        # 9. 更新状态 → continue
