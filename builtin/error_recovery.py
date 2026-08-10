"""模型调用的错误恢复工具。

本模块把重试、降级和续写策略从具体 API 适配器中拆出来。调用方只需要传入
一个无参数函数，恢复流程会在处理瞬态错误时同步更新共享的 ``RecoveryState``。
"""

import random
import time

import config


model_config = config.Config().get_model_config()
default_content_length = config.Config().get_content_length()

# 临时故障处理
BASE_DELAY_MS = 500         # 基础重试延迟（毫秒）
MAX_CONSECUTIVE_529 = 3     # 最大连续 529 错误次数
CONTINUATION_PROMPT = (
    "Output token limit reached. Continue directly from where you stopped. "
    "Do not apologize, recap, or restart."
)
MAX_RETRIES = 3             # 最大重试次数
MAX_RECOVERY_RETRIES = 3    # 最大恢复重试次数


# ============================================================
# 错误恢复 Error Recovery
# ============================================================

class RecoveryState:
    """重试和输出恢复流程共享的可变状态。

    Attributes:
        has_escalated: 输出 token 恢复是否已经进入升级状态。
        recovery_count: 升级后已经追加的续写提示次数。
        consecutive_529: ``with_retry`` 已连续遇到的过载错误次数。
        has_attempted_reactive_compact: 预留给调用方的标记，用于记录是否已在
            prompt 过长后尝试过上下文压缩。
        current_model: 后续调用当前应使用的模型名称。
    """

    def __init__(self):
        # 跟踪整个循环中的恢复尝试。
        self.has_escalated = False      # 是否已升级到应急状态
        self.recovery_count = 0         # 已尝试的恢复次数
        self.consecutive_529 = 0        # 连续 529 错误次数计数
        self.has_attempted_reactive_compact = False     # 是否已尝试过恢复前压缩
        self.current_model = model_config["model_name"] # 当前使用的模型


# 设置重试延迟
def retry_delay(attempt, retry_after=None):
    """返回下一次重试前需要等待的秒数。

    上游 API 返回的 ``retry_after`` 优先级最高。否则使用带上限的指数退避，
    并加入最高 25% 的随机抖动。
    """

    if retry_after:
        return retry_after
    base = min(BASE_DELAY_MS * (2**attempt), 32000) / 1000
    jitter = random.uniform(0, base * 0.25)
    return base + jitter


# 重试装饰器
# 瞬态错误使用指数退避（429/529）。
# 非瞬态错误会重新抛出给外部处理程序。
def with_llm_retry(fn, state, RunPolicy):
    """ 执行 ``fn``，并处理限流和过载这类瞬态错误。

    限流错误通过异常类名中的 ``RateLimit`` 或异常消息中的 ``429`` 识别。
    过载错误通过异常类名中的 ``Overloaded``，或异常消息中的 ``529`` /
    ``overloaded`` 识别。其他异常会立即重新抛出。

    连续过载达到阈值后，如果配置了 fallback 模型，会把 ``state.current_model``
    切换为该模型。
    """

    for attempt in range(MAX_RETRIES):
        # 尝试执行函数
        try:
            result = fn()
            state.consecutive_529 = 0
            return result
        except Exception as e:
            name = type(e).__name__
            msg = str(e).lower()

            # 处理 429 限流错误
            if "ratelimit" in name.lower() or "429" in msg:
                delay = retry_delay(attempt)
                print(
                    f"  \033[33m[429 rate limit] retry {attempt + 1}/{MAX_RETRIES} "
                    f"wait {delay:.1f}s\033[0m"
                )
                time.sleep(delay)
                continue

            # 处理 529 过载错误
            if "overloaded" in name.lower() or "529" in msg or "overloaded" in msg:
                state["consecutive_529"] += 1
                if state["consecutive_529"] >= MAX_CONSECUTIVE_529:
                    if RunPolicy["fallback_model"]:
                        state["current_model"] = dict(RunPolicy["fallback_model"])
                        state["consecutive_529"] = 0
                        print(
                            f"  \033[33m[529 x{MAX_CONSECUTIVE_529}] "
                            f"switching to fallback model "
                            f"{RunPolicy['fallback_model']['model_name']} and retrying\033[0m"
                        )
                    else:
                        state["consecutive_529"] = 0
                        print(
                            f"  \033[33m[529 x{MAX_CONSECUTIVE_529}] "
                            "no fallback model configured; retrying\033[0m"
                        )
                delay = retry_delay(attempt)
                print(
                    f"  \033[33m[529 overloaded] retry {attempt + 1}/{MAX_RETRIES} "
                    f"wait {delay:.1f}s\033[0m"
                )
                time.sleep(delay)
                continue

            raise
    raise RuntimeError(f"Exceeded max retry attempts ({MAX_RETRIES}) without success.")


# 重试装饰器
# 瞬态错误使用指数退避（429/529）。
# 非瞬态错误会重新抛出给外部处理程序。
def with_retry(fn, state: RecoveryState):
    """执行 ``fn``，并处理限流和过载这类瞬态错误。（旧版）

    限流错误通过异常类名中的 ``RateLimit`` 或异常消息中的 ``429`` 识别。
    过载错误通过异常类名中的 ``Overloaded``，或异常消息中的 ``529`` /
    ``overloaded`` 识别。其他异常会立即重新抛出。

    连续过载达到阈值后，如果配置了 fallback 模型，会把 ``state.current_model``
    切换为该模型。
    """

    for attempt in range(MAX_RETRIES):
        # 尝试执行函数
        try:
            result = fn()
            state.consecutive_529 = 0
            return result
        except Exception as e:
            name = type(e).__name__
            msg = str(e).lower()

            # 处理 429 限流错误
            if "ratelimit" in name.lower() or "429" in msg:
                delay = retry_delay(attempt)
                print(
                    f"  \033[33m[429 rate limit] retry {attempt + 1}/{MAX_RETRIES} "
                    f"wait {delay:.1f}s\033[0m"
                )
                time.sleep(delay)
                continue

            # 处理 529 过载错误
            if "overloaded" in name.lower() or "529" in msg or "overloaded" in msg:
                state.consecutive_529 += 1
                if state.consecutive_529 >= MAX_CONSECUTIVE_529:
                    if model_config["fallback_model_name"]:
                        state.current_model = model_config["fallback_model_name"]
                        state.consecutive_529 = 0
                        print(
                            f"  \033[33m[529 x{MAX_CONSECUTIVE_529}] "
                            f"switching to fallback model "
                            f"{model_config['fallback_model_name']} and retrying\033[0m"
                        )
                    else:
                        state.consecutive_529 = 0
                        print(
                            f"  \033[33m[529 x{MAX_CONSECUTIVE_529}] "
                            "no fallback model configured; retrying\033[0m"
                        )
                delay = retry_delay(attempt)
                print(
                    f"  \033[33m[529 overloaded] retry {attempt + 1}/{MAX_RETRIES} "
                    f"wait {delay:.1f}s\033[0m"
                )
                time.sleep(delay)
                continue

            raise
    raise RuntimeError(f"Exceeded max retry attempts ({MAX_RETRIES}) without success.")


# ---------------------- 提示词超限处理 ----------------------
def is_prompt_too_long_error(e: Exception) -> bool:
    """判断异常是否像 prompt 或上下文长度超限错误。"""

    msg = str(e).lower()
    return (
        ("prompt" in msg and "long" in msg)
        or "prompt is too long" in msg
        or "context_length_exceeded" in msg
        or "max_context_window" in msg
        or "exceed_context_size" in msg
    )


# ----------------------- 输出截断处理 -----------------------

# Path 1: 输出截断恢复：提升 max_tokens 大小，或追加续写提示继续恢复
def output_tokens_too_long_error(messages: list, state):
    """处理输出被截断的情况：先升级一次输出预算，然后追加续写提示。

    第一次调用只把状态标记为已升级，方便调用方提高输出 token 预算。后续调用会
    追加续写提示，直到达到 ``MAX_RECOVERY_RETRIES``。
    """

    # 如果未升级到应急状态，则先升级到应急状态（提高 max_tokens 大小）。
    if not state["max_output_tokens_override"]:
        state["max_output_tokens_override"] = True
        print(
            "  \033[33m[max_tokens] escalating output budget "
            f"{default_content_length['MAIN_OUTPUT_TOKENS']} -> "
            f"{default_content_length['ESCALATED_MAX_OUTPUT_TOKENS']}\033[0m"
        )
        return state, messages

    # 如果未超过最大恢复次数，则继续恢复。
    if state["recovery_count"] < MAX_RECOVERY_RETRIES:
        messages.append({"role": "user", "content": CONTINUATION_PROMPT})
        state["recovery_count"] += 1
        print(f"  \033[33m[max_tokens] continuing {state['recovery_count']}/{MAX_RECOVERY_RETRIES}\033[0m")
        return state, messages

    # 如果已超过最大恢复次数，则提示用户。
    print("  \033[31m[max_tokens] reached max recovery attempts.\033[0m")
    return state, messages


# Path 1: 输出截断恢复：提升 max_tokens 大小，或追加续写提示继续恢复
def max_tokens_too_long_error(messages: list, state: RecoveryState):
    """处理输出被截断的情况：先升级一次输出预算，然后追加续写提示。（旧版）

    第一次调用只把状态标记为已升级，方便调用方提高输出 token 预算。后续调用会
    追加续写提示，直到达到 ``MAX_RECOVERY_RETRIES``。
    """

    # 如果未升级到应急状态，则先升级到应急状态（提高 max_tokens 大小）。
    if not state.has_escalated:
        state.has_escalated = True
        print(
            "  \033[33m[max_tokens] escalating output budget "
            f"{default_content_length['MAIN_OUTPUT_TOKENS']} -> "
            f"{default_content_length['ESCALATED_MAX_OUTPUT_TOKENS']}\033[0m"
        )
        return state, messages

    # 如果未超过最大恢复次数，则继续恢复。
    if state.recovery_count < MAX_RECOVERY_RETRIES:
        messages.append({"role": "user", "content": CONTINUATION_PROMPT})
        state.recovery_count += 1
        print(f"  \033[33m[max_tokens] continuing {state.recovery_count}/{MAX_RECOVERY_RETRIES}\033[0m")
        return state, messages

    # 如果已超过最大恢复次数，则提示用户。
    print("  \033[31m[max_tokens] reached max recovery attempts.\033[0m")
    return state, messages
