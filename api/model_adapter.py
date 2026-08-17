"""模型 API 适配器的公共方法。

用于把统一的 ``ModelRequest`` 转换成不同厂商的请求格式，
再把厂商响应转换成统一的 ``ModelResponse``。

Typical usage example:
```
    response = adapter.complete(request)
```
"""

import base64
import json
from typing import Any

from .contract import ModelRequest, ModelResponse


class ModelAdapter:
    """所有模型适配器共用的简单调用流程。

    子类只需要实现请求转换、SDK 调用和响应转换三个方法。
    """

    def encode_request(self, request: ModelRequest) -> Any:
        """将内部请求转换成厂商请求。

        Args:
            request: 项目内部统一请求。

        Returns:
            Any: 厂商 SDK 可以直接使用的请求参数。

        Raises:
            NotImplementedError: 子类没有实现该方法时抛出。
        """
        raise NotImplementedError

    def send(self, payload: Any) -> Any:
        """调用厂商 SDK。

        Args:
            payload: ``encode_request`` 生成的厂商请求。

        Returns:
            Any: 厂商 SDK 返回的原始响应。

        Raises:
            NotImplementedError: 子类没有实现该方法时抛出。
        """
        raise NotImplementedError

    def decode_response(self, raw_response: Any) -> ModelResponse:
        """将厂商响应转换成内部响应。

        Args:
            raw_response: 厂商 SDK 返回的原始响应对象。

        Returns:
            ModelResponse: 项目内部统一响应。

        Raises:
            NotImplementedError: 子类没有实现该方法时抛出。
        """
        raise NotImplementedError

    def complete(self, request: ModelRequest) -> ModelResponse:
        """完成一次完整模型调用。

        Args:
            request: 项目内部统一请求。

        Returns:
            ModelResponse: 转换后的统一响应。
        """
        # 第一步：把内部请求转换成当前厂商的请求格式。
        payload = self.encode_request(request)
        # 第二步：调用厂商 SDK，取得原始响应。
        response = self.send(payload)
        # 第三步：把原始响应转换回项目内部格式。
        return self.decode_response(response)


def get_value(value: Any, key: str, default: Any = None) -> Any:
    """兼容读取字典字段和对象属性。

    Args:
        value: 要读取的字典或 SDK 响应对象。
        key: 字段名称或属性名称。
        default: 字段不存在时返回的默认值。

    Returns:
        Any: 读取到的字段值。
    """
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def json_text(value: Any) -> str:
    """将值转换成 JSON 字符串。

    Args:
        value: 通常是工具调用参数字典。

    Returns:
        str: JSON 格式的字符串。
    """
    return json.dumps(value or {}, ensure_ascii=False)


def tool_schema(tool: dict[str, Any]) -> dict[str, Any]:
    """读取工具参数 schema。

    Args:
        tool: 当前项目使用的工具定义字典。

    Returns:
        dict[str, Any]: 工具的输入参数 schema。
    """
    return tool.get(
        "input_schema",
        {"type": "object", "properties": {}},
    )


def decode_data_uri(uri: str) -> tuple[str, bytes]:
    """解析简单的 base64 图片 data URI。

    Args:
        uri: 形如 ``data:image/png;base64,...`` 的图片字符串。

    Returns:
        tuple[str, bytes]: 图片媒体类型和解码后的二进制数据。

    Raises:
        ValueError: URI 格式不正确或 base64 解码失败时抛出。
    """
    header, encoded = uri.split(",", 1)
    media_type = header[5:].split(";", 1)[0]
    return media_type, base64.b64decode(encoded)
