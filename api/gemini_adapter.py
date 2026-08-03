"""Gemini GenerateContent API 适配器。

用于调用 Gemini GenerateContent 接口，并把 Gemini 的 Content、Part
和 function call 转换成项目内部使用的响应格式。

Typical usage example:
```
    adapter = GeminiAdapter.from_model_config(model_info)
    response = adapter.complete(request)
```
"""

from typing import Any

from google import genai
from google.genai import types

from .contract import ModelRequest, ModelResponse, TextPart, ToolCallPart
from .model_adapter import (
    ModelAdapter,
    decode_data_uri,
    get_value,
    tool_schema,
)


class GeminiAdapter(ModelAdapter):
    """调用 Gemini GenerateContent API。

    Gemini 不使用 OpenAI 风格的 message 字典，而是使用 Content 和 Part，
    因此本适配器的主要工作是转换消息和工具调用。
    """

    def __init__(self, client: Any):
        """保存 Gemini 客户端。

        Args:
            client: Gemini SDK 客户端。测试时可以传入 fake client。
        """
        self.client = client

    @classmethod
    def from_model_config(cls, model_info: dict[str, Any]):
        """根据项目当前的模型配置创建适配器。

        Args:
            model_info: 包含 ``api_key`` 和可选 ``model_url`` 的配置。

        Returns:
            GeminiAdapter: 已初始化的 Gemini 适配器。
        """
        client_args = {"api_key": model_info["api_key"]}
        model_url = model_info.get("model_url")
        if model_url and model_url != "http://localhost:8000":
            # 项目默认的 localhost 是 OpenAI/Anthropic 兼容服务，
            # 不应该直接作为 Gemini 的 base_url。
            client_args["http_options"] = types.HttpOptions(base_url=model_url)
        return cls(genai.Client(**client_args))

    def encode_request(self, request: ModelRequest) -> dict[str, Any]:
        """将内部请求转换成 Gemini GenerateContent 请求。

        Args:
            request: 项目内部统一请求。

        Returns:
            dict[str, Any]: 可以传给 ``generate_content`` 的请求参数。
        """
        config_args = {"max_output_tokens": request.max_tokens}
        if request.system_prompt:
            # Gemini 将系统提示词放入 GenerateContentConfig。
            config_args["system_instruction"] = request.system_prompt
        if request.tools:
            # Gemini 工具定义放在 function_declarations 中。
            config_args["tools"] = [
                types.Tool(
                    function_declarations=[
                        self._convert_tool(tool) for tool in request.tools
                    ]
                )
            ]
        return {
            "model": request.model,
            "contents": self._convert_messages(request.messages),
            "config": types.GenerateContentConfig(**config_args),
        }

    def send(self, payload: dict[str, Any]) -> Any:
        """调用 Gemini GenerateContent API。

        Args:
            payload: ``encode_request`` 生成的请求参数。

        Returns:
            Any: Gemini SDK 返回的原始响应。
        """
        return self.client.models.generate_content(**payload)

    def decode_response(self, raw_response: Any) -> ModelResponse:
        """将 Gemini 响应转换成统一响应。

        Args:
            raw_response: Gemini SDK 返回的响应对象。

        Returns:
            ModelResponse: 包含文本和工具调用的统一响应。
        """
        content = []
        if getattr(raw_response, "text", ""):
            # Gemini 的 text 属性是最简单的文本响应入口。
            content.append(TextPart(text=raw_response.text))

        # 某些 SDK 版本通过 function_calls 属性提供工具调用。
        calls = self._get_function_calls(raw_response)
        for index, call in enumerate(calls):
            content.append(
                ToolCallPart(
                    id=get_value(call, "id", f"gemini-tool-{index}"),
                    name=get_value(call, "name", ""),
                    input=get_value(call, "args", {}) or {},
                    thought_signature=get_value(call, "thought_signature"),
                )
            )

        usage = get_value(raw_response, "usage_metadata")
        usage = vars(usage) if usage and not isinstance(usage, dict) else usage
        stop_reason = "tool_use" if calls else "end_turn"
        return ModelResponse(content=content, stop_reason=stop_reason, usage=usage)

    def _convert_messages(self, messages: list[dict[str, Any]]) -> list[types.Content]:
        """将内部消息转换成 Gemini Content。

        Args:
            messages: 当前项目使用的内部消息字典列表。

        Returns:
            list[types.Content]: Gemini SDK 使用的 Content 列表。
        """
        converted = []
        tool_names = {}

        for message in messages:
            # Gemini 使用 model 表示 assistant，其他消息统一作为 user。
            role = "model" if message.get("role") == "assistant" else "user"
            parts = []
            for block in message.get("content", []) if isinstance(message.get("content"), list) else [message.get("content", "")]:
                block_type = get_value(block, "type")
                if block_type == "text" or isinstance(block, str):
                    # 普通文本直接转换为 Gemini Part。
                    parts.append(types.Part(text=get_value(block, "text", block)))
                elif block_type == "tool_use":
                    # 保存 id 到 name 的映射，tool_result 只提供 id 时可以找回函数名。
                    tool_id = get_value(block, "id")
                    tool_names[tool_id] = get_value(block, "name")
                    call = types.Part.from_function_call(
                        name=get_value(block, "name"),
                        args=get_value(block, "input", {}) or {},
                    )
                    call.function_call.id = tool_id
                    signature = get_value(block, "thought_signature")
                    if signature:
                        call.thought_signature = signature
                    parts.append(call)
                elif block_type == "tool_result":
                    # Gemini 的 function_response 使用函数名，不使用 tool_use_id。
                    tool_id = get_value(block, "tool_use_id")
                    result = types.Part.from_function_response(
                        name=tool_names.get(tool_id, tool_id or "tool_result"),
                        response={"result": str(get_value(block, "content", ""))},
                    )
                    result.function_response.id = tool_id
                    parts.append(result)
                elif block_type == "image":
                    media_type, data = decode_data_uri(get_value(block, "uri", ""))
                    parts.append(types.Part.from_bytes(data=data, mime_type=media_type))

            if parts:
                converted.append(types.Content(role=role, parts=parts))
        return converted

    @staticmethod
    def _convert_tool(tool: dict[str, Any]) -> dict[str, Any]:
        """将内部工具定义转换成 Gemini 函数定义。

        Args:
            tool: 当前项目使用的工具定义字典。

        Returns:
            dict[str, Any]: Gemini function declaration 格式的字典。
        """
        return {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool_schema(tool),
        }

    @staticmethod
    def _get_function_calls(response: Any) -> list[Any]:
        """兼容读取 Gemini 的几种工具调用返回形式。

        Args:
            response: Gemini SDK 返回的响应对象。

        Returns:
            list[Any]: Gemini 返回的 function call 对象列表。
        """
        calls = []
        for candidate in get_value(response, "candidates", []) or []:
            content = get_value(candidate, "content")
            for part in get_value(content, "parts", []) or []:
                function_call = get_value(part, "function_call")
                if function_call:
                    if get_value(function_call, "thought_signature") is None:
                        function_call.thought_signature = get_value(
                            part, "thought_signature"
                        )
                    calls.append(function_call)
        if calls:
            return calls
        return get_value(response, "function_calls", []) or []
