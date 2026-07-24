""" 调用模型接口 Modules.

用于调用不同厂家的模型接口。

Typical usage example:
```
    call_model(messages)
```

"""

import config
from .anthropic_api import call_anthropic_model


# 模型模式选择
model_pattern = ["default",
                 "summary"]


def get_model_config():
    """ 获取模型相关配置
    
    获取需要的模型相关配置的项目，例如 "MODEL"、"MAX_OUTPUT_TOKENS" 等。
    
    Returns:
        dict: 模型相关字典
    """
    model_config = config.Config().get_model_config()
    default_content_length = config.Config().get_content_length()
    
    return model_config, default_content_length

def call_model(messages: list = [], 
               system_prompt: str = "", 
               tools: list = [], 
               model_pattern: str = "default"):
    """ 调用模型接口 object.

    该函数负责调用不同厂家的模型接口。

    Args:
        messages: 包含用户输入和模型输出的消息列表。
        system_prompt: 系统提示。
        tools: 工具列表。
        model_pattern: 模型模式。

    Returns:
        response：模型输出。
    Raises:
        ValueError: 不支持的 API 接口。
    """

    # 配置默认模型上下文窗口大小
    model_config, default_content_length = get_model_config()
    api = model_config["api"]

    # 调用不同厂家的模型接口
    if api == "openai":
        pass
    elif api == "anthropic":
        response = call_anthropic_model(model_info = model_config,
                                        content_info = default_content_length,
                                        messages = messages,
                                        system_prompt = system_prompt,
                                        tools = tools,
                                        model_pattern = model_pattern)
    else:
        raise ValueError("不支持的 API 接口。")
    
    return response