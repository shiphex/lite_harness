"""模型响应适配工具.

用于把不同厂商的响应统一转换成当前 Agent 循环可消费的格式。
"""

from types import SimpleNamespace


def get_value(value, key: str, default=None):
    """兼容读取 dict 字段和对象属性。"""
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def make_text_block(text: str):
    """创建文本 block。"""
    return SimpleNamespace(type="text", text=text)


def make_tool_use_block(tool_id: str, name: str, tool_input: dict):
    """创建工具调用 block。"""
    return SimpleNamespace(
        type="tool_use",
        id=tool_id,
        name=name,
        input=tool_input or {},
    )


def make_model_response(content: list, stop_reason: str = "end_turn"):
    """创建主循环需要的模型响应对象。"""
    return SimpleNamespace(content=content, stop_reason=stop_reason)


def get_max_tokens(content_info: dict, model_pattern: str):
    """根据模型模式选择输出 token 数。"""
    if model_pattern == "summary":
        return content_info["SUMMARY_OUTPUT_TOKENS"]
    return content_info["MAIN_OUTPUT_TOKENS"]


def normalize_json_schema(schema):
    """补全空的工具入参 schema。"""
    if not schema:
        return {"type": "object", "properties": {}}
    return schema


def anthropic_tools_to_openai_tools(tools: list):
    """将 Anthropic 风格工具定义转换成 OpenAI tools 格式。"""
    openai_tools = []
    for tool in tools or []:
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": normalize_json_schema(tool.get("input_schema")),
                },
            }
        )
    return openai_tools


def anthropic_tools_to_function_declarations(tools: list):
    """将 Anthropic 风格工具定义转换成 function declaration。"""
    declarations = []
    for tool in tools or []:
        declarations.append(
            {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": normalize_json_schema(tool.get("input_schema")),
            }
        )
    return declarations
