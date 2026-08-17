"""OpenAI Chat Completions API 适配器。

用于调用 OpenAI Chat Completions 接口，兼容使用相同接口格式的本地服务。

Typical usage example:
```
    adapter = OpenAIAdapter.from_model_config(model_info)
    response = adapter.complete(request)
```
"""

import json
from typing import Any

from openai import OpenAI

from .contract import ModelRequest, ModelResponse, TextPart, ToolCallPart
from .model_adapter import ModelAdapter, get_value, json_text, tool_schema


class OpenAIAdapter(ModelAdapter):
    """调用 OpenAI Chat Completions API。

    本适配器只处理 Chat Completions，不处理 OpenAI Responses API。
    """

    def __init__(self, client: Any):
        """保存 OpenAI 客户端。

        Args:
            client: OpenAI SDK 客户端。测试时可以传入 fake client。
        """
        self.client = client

    @classmethod
    def from_model_config(cls, model_info: dict[str, Any]):
        """根据项目当前的模型配置创建适配器。

        Args:
            model_info: 包含 ``model_url`` 和 ``api_key`` 的模型配置。

        Returns:
            OpenAIAdapter: 已初始化的 OpenAI 适配器。
        """
        client = OpenAI(
            base_url=model_info["model_url"],
            api_key=model_info["api_key"],
        )
        return cls(client)

    def encode_request(self, request: ModelRequest) -> dict[str, Any]:
        """将内部请求转换成 OpenAI Chat Completions 请求。

        Args:
            request: 项目内部统一请求。

        Returns:
            dict[str, Any]: 可以传给 ``chat.completions.create`` 的请求参数。
        """
        messages = []
        if request.system_prompt:
            # OpenAI 使用一条 role 为 system 的消息保存系统提示词。
            messages.append({"role": "system", "content": request.system_prompt})
        for message in request.messages:
            # 普通消息和工具消息交给单独的转换函数处理。
            messages.extend(self._convert_message(message))

        payload = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens,
        }
        if request.tools:
            # OpenAI 的工具定义需要包在 type=function 和 function 中。
            payload["tools"] = [self._convert_tool(tool) for tool in request.tools]
        return payload

    def send(self, payload: dict[str, Any]) -> Any:
        """调用 OpenAI Chat Completions API。

        Args:
            payload: ``encode_request`` 生成的请求参数。

        Returns:
            Any: OpenAI SDK 返回的原始响应。
        """
        return self.client.chat.completions.create(**payload)

    def decode_response(self, raw_response: Any) -> ModelResponse:
        """将 OpenAI 响应转换成统一响应。

        Args:
            raw_response: OpenAI SDK 返回的响应对象。

        Returns:
            ModelResponse: 包含文本、工具调用和结束原因的统一响应。
        """
        choice = raw_response.choices[0]
        message = choice.message
        content = []

        if message.content:
            # OpenAI 返回的普通文本转换成内部 TextPart。
            content.append(TextPart(text=message.content))

        for tool_call in message.tool_calls or []:
            # OpenAI 的 function.arguments 是 JSON 字符串，先解析成字典。
            try:
                arguments = json.loads(tool_call.function.arguments)
            except (TypeError, json.JSONDecodeError):
                arguments = {}
            content.append(
                ToolCallPart(
                    id=tool_call.id,
                    name=tool_call.function.name,
                    input=arguments,
                )
            )

        usage = get_value(raw_response, "usage")
        usage = vars(usage) if usage and not isinstance(usage, dict) else usage
        stop_reason = "tool_use" if message.tool_calls else choice.finish_reason
        return ModelResponse(content=content, stop_reason=stop_reason, usage=usage)

    def _convert_message(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        """将一条内部字典消息转换成 OpenAI 消息。

        Args:
            message: 当前项目使用的内部消息字典。

        Returns:
            list[dict[str, Any]]: OpenAI 消息列表。

        之所以返回列表，是因为一条包含 tool_result 的内部消息，
        可能需要拆成多条 OpenAI tool 消息。
        """
        role = message.get("role")
        content = message.get("content")

        if role == "assistant" and isinstance(content, list):
            # assistant 消息可能同时包含文本和多个工具调用。
            text = self._content_to_text(content)
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
                            "arguments": json_text(get_value(block, "input", {})),
                        },
                    }
                )
            result = {"role": "assistant", "content": text or None}
            if tool_calls:
                result["tool_calls"] = tool_calls
            return [result]

        if role == "user" and isinstance(content, list):
            # user 消息中的 tool_result 需要转换成 role=tool 的消息。
            result = []
            text_parts = []
            for block in content:
                if get_value(block, "type") == "tool_result":
                    result.append(
                        {
                            "role": "tool",
                            "tool_call_id": get_value(block, "tool_use_id"),
                            "content": str(get_value(block, "content", "")),
                        }
                    )
                else:
                    text_parts.append(str(block))
            if text_parts:
                result.insert(0, {"role": "user", "content": "\n".join(text_parts)})
            return result

        return [{"role": role, "content": self._content_to_text(content)}]

    @staticmethod
    def _content_to_text(content: Any) -> str:
        """从内部 content 中提取纯文本。

        Args:
            content: 字符串、内容块列表或其他消息内容。

        Returns:
            str: 提取出的文本。
        """
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return str(content)
        return "".join(
            str(get_value(block, "text", ""))
            for block in content
            if get_value(block, "type") == "text"
        )

    @staticmethod
    def _convert_tool(tool: dict[str, Any]) -> dict[str, Any]:
        """将内部工具定义转换成 OpenAI 工具定义。

        Args:
            tool: 当前项目使用的工具定义字典。

        Returns:
            dict[str, Any]: OpenAI function tool 格式的字典。
        """
        return {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool_schema(tool),
            },
        }
