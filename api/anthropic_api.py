""" Anthropic API Modules.

用于调用 Anthropic 模型接口。

Typical usage example:
```
    call_model(messages)
```
"""

from anthropic import Anthropic

# 加载环境变量
ANTHROPIC_BASE_URL = "http://localhost:8000"
ANTHROPIC_API_KEY = "no-key"
client = Anthropic(base_url = ANTHROPIC_BASE_URL, api_key = ANTHROPIC_API_KEY)       # 使用本地部署的大模型
MODEL = "claude-fable-5" # "Qwen3.5-4B-UD-Q6_K_XL"


def call_anthropic_model(model: str = MODEL, 
                         messages: list = [], 
                         system_prompt: str = "你是一个专业的问答助手。", 
                         tools: list = [],
                         max_tokens: int = 2048):
    """ 调用 Anthropic 模型接口 object.
    
    调用 Anthropic 模型接口，返回模型输出。

    Args:
        model: 调用的模型名称。
        messages: 包含用户输入和模型输出的消息列表。
        system_prompt: 系统提示。
        tools: 工具列表。
        max_tokens: 最大输出 token 数。
    
    Returns:
        response: 模型输出。
    
    """
    response = client.messages.create(
        model = model,
        messages = messages,
        system = system_prompt,
        tools = tools,
        max_tokens = max_tokens,
    )

    return response