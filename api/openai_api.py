"""OpenAI API Modules.

用于调用 OpenAI 兼容的 Chat Completions 接口。

Typical usage example:
```
    call_openai_model(messages)
```
"""

import json

from openai import OpenAI

from .response_adapter import (
    anthropic_tools_to_openai_tools,
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
    return "".join(texts)


def _tool_arguments(tool_input):
    """将工具输入转换成 OpenAI 要求的 JSON 字符串。"""
    try:
        return json.dumps(tool_input or {}, ensure_ascii=False)
    except TypeError:
        return json.dumps({}, ensure_ascii=False)


def _convert_messages(messages: list, system_prompt: str):
    """将内部消息格式转换成 OpenAI Chat Completions 消息格式。"""
    converted = []
    if system_prompt:
        converted.append({"role": "system", "content": system_prompt})

    for message in messages or []:
        role = message.get("role")
        content = message.get("content")

        # assistant 消息中可能同时包含文本和工具调用。
        if role == "assistant" and isinstance(content, list):
            text = _content_to_text(content)
            tool_calls = []
            for block in content:
                if get_value(block, "type") != "tool_use":
                    continue
                tool_calls.append(
                    {
                        "id": get_value(block, "id"),
                        "type": "function",
                        "function": {
                            "name": get_value(block, "name"),
                            "arguments": _tool_arguments(get_value(block, "input", {})),
                        },
                    }
                )

            next_message = {"role": "assistant", "content": text or None}
            if tool_calls:
                next_message["tool_calls"] = tool_calls
            converted.append(next_message)
            continue

        # user 消息中的 tool_result 需要拆成 OpenAI 的 tool 消息。
        if role == "user" and isinstance(content, list):
            tool_result_messages = []
            other_text = []
            for block in content:
                if get_value(block, "type") == "tool_result":
                    tool_result_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": get_value(block, "tool_use_id"),
                            "content": str(get_value(block, "content", "")),
                        }
                    )
                else:
                    other_text.append(str(block))

            if other_text:
                converted.append({"role": "user", "content": "\n".join(other_text)})
            converted.extend(tool_result_messages)
            continue

        converted.append({"role": role, "content": _content_to_text(content)})

    return converted


def _parse_tool_input(arguments):
    """解析 OpenAI 返回的工具参数。"""
    if not arguments:
        return {}
    try:
        parsed = json.loads(arguments)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _adapt_response(response):
    """将 OpenAI 返回值转换成当前主循环使用的响应格式。"""
    choice = response.choices[0]
    message = choice.message
    content = []

    if getattr(message, "content", None):
        content.append(make_text_block(message.content))

    tool_calls = getattr(message, "tool_calls", None) or []
    for tool_call in tool_calls:
        function = tool_call.function
        content.append(
            make_tool_use_block(
                tool_id=tool_call.id,
                name=function.name,
                tool_input=_parse_tool_input(function.arguments),
            )
        )

    stop_reason = "tool_use" if tool_calls else "end_turn"
    return make_model_response(content, stop_reason)


def call_openai_model(
    model_info: dict,
    content_info: dict,
    messages: list = [],
    system_prompt: str = "",
    tools: list = [],
    model_pattern: str = "default",
):
    """调用 OpenAI 兼容模型接口 object."""
    # 初始化 OpenAI 客户端。
    client = OpenAI(
        base_url=model_info["model_url"],
        api_key=model_info["api_key"],
    )
    max_tokens = get_max_tokens(content_info, model_pattern)
    openai_tools = anthropic_tools_to_openai_tools(tools)

    # 组装请求参数，tools 为空时不传入 tools 字段。
    request = {
        "model": model_info["model_name"],
        "messages": _convert_messages(messages, system_prompt),
        "max_tokens": max_tokens,
    }
    if openai_tools:
        request["tools"] = openai_tools

    # 调用模型接口，并统一返回格式。
    response = client.chat.completions.create(**request)
    return _adapt_response(response)
