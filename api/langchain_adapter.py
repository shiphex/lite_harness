"""Adapter for the existing LangChain model integration."""

from typing import Any

import config

from .contract import ModelRequest, ModelResponse, TextPart, ToolCallPart
from .old_api.langchain_api import call_langchain_model
from .model_adapter import ModelAdapter, get_value


class LangChainAdapter(ModelAdapter):
    """Expose the legacy LangChain call path through ``ModelAdapter``."""

    def __init__(self, model_info: dict[str, Any]):
        self.model_info = dict(model_info)

    @classmethod
    def from_model_config(cls, model_info: dict[str, Any]):
        return cls(model_info)

    def complete(self, request: ModelRequest) -> ModelResponse:
        model_info = {**self.model_info, "model_name": request.model}
        raw_response = call_langchain_model(
            model_info=model_info,
            content_info=config.Config().get_content_length(),
            messages=request.messages,
            system_prompt=request.system_prompt,
            tools=request.tools,
            model_pattern="default",
            max_tokens=request.max_tokens,
        )

        content = []
        for block in get_value(raw_response, "content", []) or []:
            block_type = get_value(block, "type")
            if block_type == "text":
                content.append(TextPart(text=get_value(block, "text", "")))
            elif block_type == "tool_use":
                content.append(
                    ToolCallPart(
                        id=get_value(block, "id", ""),
                        name=get_value(block, "name", ""),
                        input=get_value(block, "input", {}) or {},
                    )
                )

        return ModelResponse(
            content=content,
            stop_reason=get_value(raw_response, "stop_reason", "end_turn"),
        )
