"""LangChain API Modules.

用于通过 LangChain 调用 OpenAI 后端模型。

Typical usage example:
```
    call_langchain_model(messages)
```
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from .response_adapter import (
    anthropic_tools_to_function_declarations,
    get_max_tokens,
    get_value,
    make_model_response,
    make_text_block,
    make_tool_use_block,
)


model_pattern = ["default",
                 "summary",
                 "mini",
                 "long"]


def _content_to_text(content):
    """从当前消息 content 中提取纯文本。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content)

    texts = []
    for block in content:
        block_type = get_value(block, "type")
        if block_type == "text":
            texts.append(str(get_value(block, "text", "")))
        elif isinstance(block, str):
            texts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            texts.append(str(block.get("text", "")))
    return "".join(texts)


def _convert_messages(messages: list, system_prompt: str):
    """将内部消息格式转换成 LangChain 消息对象。"""
    converted = []
    if system_prompt:
        converted.append(SystemMessage(content=system_prompt))

    for message in messages or []:
        role = message.get("role")
        content = message.get("content")

        # assistant 消息中可能同时包含文本和工具调用。
        if role == "assistant" and isinstance(content, list):
            tool_calls = []
            for block in content:
                if get_value(block, "type") != "tool_use":
                    continue
                tool_calls.append(
                    {
                        "name": get_value(block, "name"),
                        "args": get_value(block, "input", {}) or {},
                        "id": get_value(block, "id"),
                        "type": "tool_call",
                    }
                )
            converted.append(AIMessage(content=_content_to_text(content), tool_calls=tool_calls))
            continue

        # 普通 assistant 文本消息。
        if role == "assistant":
            converted.append(AIMessage(content=_content_to_text(content)))
            continue

        # user 消息中的 tool_result 需要转换成 LangChain ToolMessage。
        if role == "user" and isinstance(content, list):
            other_text = []
            for block in content:
                if get_value(block, "type") == "tool_result":
                    converted.append(
                        ToolMessage(
                            content=str(get_value(block, "content", "")),
                            tool_call_id=get_value(block, "tool_use_id"),
                        )
                    )
                else:
                    other_text.append(str(block))
            if other_text:
                converted.append(HumanMessage(content="\n".join(other_text)))
            continue

        converted.append(HumanMessage(content=_content_to_text(content)))

    return converted


def _extract_text_content(content):
    """从 LangChain AIMessage content 中提取文本。"""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content) if content else ""

    texts = []
    for block in content:
        if isinstance(block, dict):
            block_type = block.get("type")
            if block_type in ("text", "text_delta"):
                texts.append(str(block.get("text", block.get("content", ""))))
        elif isinstance(block, str):
            texts.append(block)
    return "".join(texts)


def _adapt_response(response):
    """将 LangChain 返回值转换成当前主循环使用的响应格式。"""
    content = []
    text = _extract_text_content(getattr(response, "content", ""))
    if text:
        content.append(make_text_block(text))

    tool_calls = getattr(response, "tool_calls", None) or []
    for index, tool_call in enumerate(tool_calls):
        content.append(
            make_tool_use_block(
                tool_id=get_value(tool_call, "id", None) or f"langchain-tool-{index}",
                name=get_value(tool_call, "name"),
                tool_input=get_value(tool_call, "args", {}) or {},
            )
        )

    stop_reason = "tool_use" if tool_calls else "end_turn"
    return make_model_response(content, stop_reason)


def call_langchain_model(
    model_info: dict,
    content_info: dict,
    messages: list = [],
    system_prompt: str = "",
    tools: list = [],
    model_pattern: str = "default",
    max_tokens: int | None = None,
):
    """调用 LangChain OpenAI 模型接口 object."""
    # 初始化 LangChain OpenAI 封装。
    output_tokens = max_tokens if max_tokens is not None else get_max_tokens(content_info, model_pattern)
    llm = ChatOpenAI(
        model=model_info["model_name"],
        api_key=model_info["api_key"],
        base_url=model_info["model_url"],
        max_completion_tokens=output_tokens,
    )

    declarations = anthropic_tools_to_function_declarations(tools)
    if declarations:
        # 绑定工具后，LangChain 会在 AIMessage.tool_calls 中返回工具调用。
        llm = llm.bind_tools(declarations)

    # 调用模型接口，并统一返回格式。
    response = llm.invoke(_convert_messages(messages, system_prompt))
    return _adapt_response(response)
