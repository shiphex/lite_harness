""" 调用模型接口 Modules.

用于调用不同厂家的模型接口。

Typical usage example:
```
    call_model(messages)
```

"""

from .anthropic_api import call_anthropic_model


class content_length:

    def __init__(self, ctx_tokens: int = 20480, max_tokens: int = 2048, chars_per_token_estimate: int = 1):
        """ 用于配置模型的上下文窗口大小。

        Args:
            ctx_tokens: 模型实际总上下文窗口大小。
            max_tokens: 用户设置的最大输出 token 数。
            chars_per_token_estimate: 每个 token 大约字符数。

        Returns:
            None
        Raises:
            None
        """
        # 上下文窗口大小默认配置
        self.CHARS_PER_TOKEN_ESTIMATE = chars_per_token_estimate    # 每个 token 大约 chars_per_token_estimate 个字符
        self.CTX_TOKENS = ctx_tokens                                # 总上下文窗口大小
        self.MAIN_OUTPUT_TOKENS = int(self.CTX_TOKENS * 0.25)       # 主输出预算
        self.SUMMARY_OUTPUT_TOKENS = min(int(self.CTX_TOKENS * 0.10), max_tokens) # 摘要输出预算
        self.SAFETY_TOKENS = int(self.CTX_TOKENS * 0.10)            # 安全余量

        self.MAX_INLINE_TOOL_RESULT_TOKENS = int(self.CTX_TOKENS * 0.10)                                # 单个工具调用输出结果触发值（0.1）
        self.MAIN_INPUT_BUDGET = self.CTX_TOKENS - self.MAIN_OUTPUT_TOKENS - self.SAFETY_TOKENS         # 主输入预算（0.65）
        self.SUMMARY_INPUT_BUDGET = self.CTX_TOKENS - self.SUMMARY_OUTPUT_TOKENS - self.SAFETY_TOKENS   # 触发摘要的输入预算（0.8）
        self.COMPACT_TRIGGER_TOKENS = int(self.MAIN_INPUT_BUDGET * 0.75)                                # 压缩触发阈值（0.4875）


def call_model(api: str = "anthropic", 
               model: str = "", 
               messages: list = [], 
               system_prompt: str = "", 
               tools: list = [],
               max_tokens: int = 2048 
               ):
    """ 调用模型接口 object.

    该函数负责调用不同厂家的模型接口。

    Args:
        api: 调用的 API 接口。
        model: 模型名称。
        messages: 包含用户输入和模型输出的消息列表。
        system_prompt: 系统提示。
        tools: 工具列表。
        max_tokens: 用户设置的最大输出 token 数。

    Returns:
        response：模型输出。
    Raises:
        ValueError: 不支持的 API 接口。
    """

    # 配置默认模型上下文窗口大小
    default_content_length = content_length(max_tokens = max_tokens, chars_per_token_estimate = 1)

    # 调用不同厂家的模型接口
    if api == "openai":
        pass
    elif api == "anthropic":
        response = call_anthropic_model(model, messages, system_prompt, tools, 
                                        default_content_length.MAIN_OUTPUT_TOKENS)
    else:
        raise ValueError("不支持的 API 接口。")
    
    return response