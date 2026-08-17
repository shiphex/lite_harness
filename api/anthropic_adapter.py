"""Anthropic API 适配器。

用于调用 Anthropic Messages API，并把 Anthropic 响应转换成项目内部格式。

Typical usage example:
```
    adapter = AnthropicAdapter.from_model_config(model_info)
    response = adapter.complete(request)
```
"""

from typing import Any

from anthropic import Anthropic

from .contract import ModelRequest, ModelResponse, TextPart, ToolCallPart
from .model_adapter import ModelAdapter, get_value


class AnthropicAdapter(ModelAdapter):
    """调用 Anthropic Messages API。

    Anthropic 的消息格式与当前项目已有的消息格式比较接近，
    所以请求转换主要是组装字段，响应转换主要是读取 content block。
    """

    def __init__(self, client: Any):
        """保存 Anthropic 客户端。

        Args:
            client: Anthropic SDK 客户端。测试时可以传入 fake client。
        """
        self.client = client

    @classmethod
    def from_model_config(cls, model_info: dict[str, Any]):
        """根据项目当前的模型配置创建适配器。

        Args:
            model_info: 包含 ``model_url`` 和 ``api_key`` 的模型配置。

        Returns:
            AnthropicAdapter: 已初始化的 Anthropic 适配器。
        """
        client = Anthropic(
            base_url=model_info["model_url"],
            api_key=model_info["api_key"],
        )
        return cls(client)

    def encode_request(self, request: ModelRequest) -> dict[str, Any]:
        """将内部请求转换成 Anthropic Messages 请求。

        Args:
            request: 项目内部统一请求。

        Returns:
            dict[str, Any]: 可以传给 ``client.messages.create`` 的参数。
        """
        # 当前内部消息和 Anthropic 消息格式接近，先直接复用消息列表。
        messages = []
        for message in request.messages:
            encoded_message = dict(message)
            content = encoded_message.get("content")
            if isinstance(content, list):
                encoded_message["content"] = [
                    {
                        key: value
                        for key, value in block.items()
                        if key != "thought_signature"
                    }
                    if isinstance(block, dict) else block
                    for block in content
                ]
            messages.append(encoded_message)

        payload = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens,
        }
        if request.system_prompt:
            # Anthropic 将系统提示词放在单独的 system 字段中。
            payload["system"] = request.system_prompt
        if request.tools:
            # 工具列表为空时不传入 tools 字段，保持和旧代码一致。
            payload["tools"] = request.tools
        return payload

    def send(self, payload: dict[str, Any]) -> Any:
        """调用 Anthropic Messages API。

        Args:
            payload: ``encode_request`` 生成的请求参数。

        Returns:
            Any: Anthropic SDK 返回的原始响应。
        """
        return self.client.messages.create(**payload)

    def decode_response(self, raw_response: Any) -> ModelResponse:
        """将 Anthropic 响应转换成统一响应。

        Args:
            raw_response: Anthropic SDK 返回的响应对象。

        Returns:
            ModelResponse: 包含文本块、工具调用和结束原因的统一响应。
        """
        content = []
        for block in get_value(raw_response, "content", []) or []:
            if get_value(block, "type") == "text":
                # Anthropic 文本 block 转换成内部 TextPart。
                content.append(TextPart(text=get_value(block, "text", "")))
            elif get_value(block, "type") == "tool_use":
                # Anthropic tool_use block 转换成内部 ToolCallPart。
                content.append(
                    ToolCallPart(
                        id=get_value(block, "id", ""),
                        name=get_value(block, "name", ""),
                        input=get_value(block, "input", {}) or {},
                    )
                )

        usage = get_value(raw_response, "usage")
        usage = vars(usage) if usage and not isinstance(usage, dict) else usage
        return ModelResponse(
            content=content,
            stop_reason=get_value(raw_response, "stop_reason", "unknown"),
            usage=usage,
            provider_metadata={"id": get_value(raw_response, "id")},
        )
