"""模型 API 统一使用的数据结构。

本文件只定义内部请求、响应和响应内容块，不负责调用具体模型接口。

Typical usage example:
```
    request = ModelRequest(
        model="test-model",
        messages=[{"role": "user", "content": "hello"}],
    )
```
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TextPart:
    """模型返回的文本块。

    Args:
        text: 模型返回的文本内容。
        type: 内容块类型，固定为 ``text``。
    """

    text: str
    type: str = "text"


@dataclass
class ToolCallPart:
    """模型返回的工具调用块。

    Args:
        id: 本次工具调用的唯一 ID。
        name: 模型要求调用的工具名称。
        input: 传给工具的参数字典。
        type: 内容块类型，固定为 ``tool_use``。
        thought_signature: Gemini 可能返回的思考签名，其他接口通常为空。
    """

    id: str
    name: str
    input: dict[str, Any]
    type: str = "tool_use"
    thought_signature: Any = None


ContentPart = TextPart | ToolCallPart


@dataclass
class ModelRequest:
    """适配器接收的统一请求。

    这个对象只保存一次模型调用需要的基本参数。消息和工具仍然使用
    当前项目正在使用的字典格式，这样可以减少新旧代码之间的转换。

    Args:
        model: 要调用的模型名称。
        messages: 对话消息列表。
        system_prompt: 系统提示词。
        tools: 模型可以调用的工具定义列表。
        max_tokens: 本次调用允许生成的最大 token 数。
    """

    model: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    system_prompt: str = ""
    tools: list[dict[str, Any]] = field(default_factory=list)
    max_tokens: int = 2048


@dataclass
class ModelResponse:
    """适配器返回的统一响应。

    Args:
        content: 模型返回的文本块和工具调用块。
        stop_reason: 模型结束本次生成的原因。
        usage: 厂商返回的 token 使用量，没有返回时为 ``None``。
        provider_metadata: 厂商特有的附加信息。
    """

    content: list[ContentPart]
    stop_reason: str
    usage: dict[str, Any] | None = None
    provider_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """提取响应中的文本。

        Returns:
            str: 按原顺序拼接后的文本。
        """
        return "".join(
            part.text
            for part in self.content
            if isinstance(part, TextPart)
        )

    @property
    def tool_calls(self) -> list[ToolCallPart]:
        """提取响应中的工具调用。

        Returns:
            list[ToolCallPart]: 响应中所有的工具调用块。
        """
        return [
            part
            for part in self.content
            if isinstance(part, ToolCallPart)
        ]
