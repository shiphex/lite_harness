"""Gemini API Modules.

用于调用 Gemini generate_content 接口。

Typical usage example:
```
    call_gemini_model(messages)
```
"""

from google import genai
from google.genai import types

from .response_adapter import (
    anthropic_tools_to_function_declarations,
    get_max_tokens,
    get_value,
    make_model_response,
    make_text_block,
    make_tool_use_block,
)


model_pattern = ["default", "summary"]


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
        if get_value(block, "type") == "text":
            texts.append(str(get_value(block, "text", "")))
        elif isinstance(block, str):
            texts.append(block)
    return "".join(texts)


def _make_client(model_info: dict):
    """初始化 Gemini 客户端。"""
    client_kwargs = {"api_key": model_info["api_key"]}
    model_url = model_info.get("model_url")

    # 默认配置里的 localhost 是本地 OpenAI/Anthropic 兼容服务，不作为 Gemini base_url。
    if model_url and model_url != "http://localhost:8000":
        client_kwargs["http_options"] = types.HttpOptions(base_url=model_url)
    return genai.Client(**client_kwargs)


def _convert_messages(messages: list):
    """将内部消息格式转换成 Gemini Content 格式。"""
    converted = []
    tool_call_names = {}

    for message in messages or []:
        role = message.get("role")
        content = message.get("content")

        # Gemini 使用 model 表示 assistant。
        gemini_role = "model" if role == "assistant" else "user"

        if isinstance(content, list):
            parts = []
            for block in content:
                block_type = get_value(block, "type")
                if block_type == "text":
                    parts.append(types.Part(text=str(get_value(block, "text", ""))))
                elif block_type == "tool_use":
                    # 记录工具 id 到 name 的映射，后续 tool_result 需要用 name 回传。
                    tool_id = get_value(block, "id")
                    name = get_value(block, "name")
                    if tool_id:
                        tool_call_names[tool_id] = name
                    parts.append(
                        types.Part.from_function_call(
                            name=name,
                            args=get_value(block, "input", {}) or {},
                        )
                    )
                elif block_type == "tool_result":
                    # Gemini 的 function_response 使用函数名，不使用 Anthropic 的 tool_use_id。
                    tool_id = get_value(block, "tool_use_id")
                    name = tool_call_names.get(tool_id, tool_id or "tool_result")
                    parts.append(
                        types.Part.from_function_response(
                            name=name,
                            response={"result": str(get_value(block, "content", ""))},
                        )
                    )
                elif isinstance(block, str):
                    parts.append(types.Part(text=block))

            if parts:
                converted.append(types.Content(role=gemini_role, parts=parts))
            continue

        text = _content_to_text(content)
        if text:
            converted.append(types.Content(role=gemini_role, parts=[types.Part(text=text)]))

    return converted


def _make_config(content_info: dict, system_prompt: str, tools: list, model_pattern: str):
    """构造 Gemini 生成配置。"""
    config_kwargs = {
        "maxOutputTokens": get_max_tokens(content_info, model_pattern),
    }
    if system_prompt:
        config_kwargs["systemInstruction"] = system_prompt

    declarations = anthropic_tools_to_function_declarations(tools)
    if declarations:
        # Gemini 工具定义放在 function_declarations 中。
        config_kwargs["tools"] = [
            types.Tool(function_declarations=declarations)
        ]

    return types.GenerateContentConfig(**config_kwargs)


def _extract_function_calls(response):
    """兼容提取 Gemini 不同形态的 function call。"""
    function_calls = getattr(response, "function_calls", None)
    if function_calls:
        return function_calls

    camel_calls = getattr(response, "functionCalls", None)
    if camel_calls:
        return camel_calls

    calls = []
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            function_call = getattr(part, "function_call", None)
            if function_call:
                calls.append(function_call)
    return calls


def _adapt_response(response):
    """将 Gemini 返回值转换成当前主循环使用的响应格式。"""
    content = []
    text = getattr(response, "text", "")
    if text:
        content.append(make_text_block(text))

    function_calls = _extract_function_calls(response)
    for index, function_call in enumerate(function_calls):
        tool_id = get_value(function_call, "id", None) or f"gemini-tool-{index}"
        content.append(
            make_tool_use_block(
                tool_id=tool_id,
                name=get_value(function_call, "name"),
                tool_input=get_value(function_call, "args", {}) or {},
            )
        )

    stop_reason = "tool_use" if function_calls else "end_turn"
    return make_model_response(content, stop_reason)


def call_gemini_model(
    model_info: dict,
    content_info: dict,
    messages: list = [],
    system_prompt: str = "",
    tools: list = [],
    model_pattern: str = "default",
):
    """调用 Gemini 模型接口 object."""
    client = _make_client(model_info)

    # 调用模型接口，并统一返回格式。
    response = client.models.generate_content(
        model=model_info["model_name"],
        contents=_convert_messages(messages),
        config=_make_config(content_info, system_prompt, tools, model_pattern),
    )
    return _adapt_response(response)
