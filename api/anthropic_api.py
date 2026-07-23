""" Anthropic API Modules.

用于调用 Anthropic 模型接口。

Typical usage example:
```
    call_model(messages)
```
"""

from anthropic import Anthropic


def call_anthropic_model(model_info: dict,
                         content_info: dict,
                         messages: list = [], 
                         system_prompt: str = "你是一个专业的问答助手。", 
                         tools: list = []):
    """ 调用 Anthropic 模型接口 object.
    
    调用 Anthropic 模型接口，返回模型输出。

    Args:
        model_info: 调用的模型信息。
        content_info: 模型上下文信息。
        messages: 包含用户输入和模型输出的消息列表。
        system_prompt: 系统提示。
        tools: 工具列表。
    
    Returns:
        response: 模型输出。
    
    """
    client = Anthropic(base_url = model_info["model_url"], api_key = model_info["api_key"])   

    response = client.messages.create(
        model = model_info["model_name"],
        messages = messages,
        system = system_prompt,
        tools = tools,
        max_tokens = content_info["MAIN_OUTPUT_TOKENS"],
    )

    return response