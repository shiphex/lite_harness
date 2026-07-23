""" 配置文件

用于存储项目的配置信息，如 API 密钥、数据库连接信息等。

Typical usage example:

"""

from pathlib import Path
import argparse


WORKDIR = Path.cwd()
# 设置默认系统提示词
DEFAULT_SYSTEM_PROMPT = (f"你是一个编码助手，位于 {WORKDIR}，当前系统环境是 Windows。使用 PowerShell 解决任务。行动，无需解释。"
                         "在开始任何多步骤任务之前，请使用 todo_write 来规划您的步骤。"
                         "随时更新状态。"
                         "对于复杂的子问题，可以使用任务工具生成子智能体。"
)

# 设置默认子智能体系统提示词
DEFAULT_SUB_SYSTEM_PROMPT = (f"你是一个编码助手，位于 {WORKDIR}，当前系统环境是 Windows。使用 PowerShell 解决任务。行动，无需解释。"
                             "完成分配给你的任务，然后提交一份简明扼要的总结。"
                             "不要再进一步委托子智能体。"
)

# 其他系统提示词
_other_prompts: dict[str, str] = {}



def parse_args(argv = None):
    """ 解析命令行参数。

    Returns:
        args_dict: 命令行参数字典
    """
    # 1. 创建解析器
    parser = argparse.ArgumentParser(description = "配置文件")
    # parser.add_argument("--config", type=str, default="config.json", help="配置文件路径")
    parser.add_argument("--chars_per_token", type = float, default = 1, help = "每个 token 大约多少个字符")
    parser.add_argument("--ctx_tokens", type = int, default = 20480, help = "总上下文窗口大小")
    parser.add_argument("--max_tokens", type = int, default = 2048, help = "最大输出 token 数量")
    parser.add_argument("--api", type = str, default = "anthropic", help = "API 名称")
    parser.add_argument("--model_url", type = str, default = "http://localhost:8000", help = "模型 URL")
    parser.add_argument("--api_key", type = str, default = "no-key", help = "模型 API 密钥")
    parser.add_argument("--model_name", type = str, default = "claude-fable-5", help = "模型名称")
    cmd_args = parser.parse_args(argv)
    # 将命令行解析出的命名空间，快速转化为标准的 Python 字典
    # 此时 args_dict = {'chars_per_token': 1.0, 'ctx_tokens': 20480, 'max_tokens': 2048, ......}
    args_dict = vars(cmd_args)

    return args_dict


_current_args = parse_args([])


def configure(argv = None):
    """Parse startup arguments and store them as the current configuration."""
    global _current_args

    _current_args = parse_args(argv)
    return get_config()


def update_config(**overrides):
    """Update selected runtime configuration values."""
    global _current_args

    unknown_keys = set(overrides) - set(_current_args)
    if unknown_keys:
        raise ValueError(f"未知配置项: {', '.join(sorted(unknown_keys))}")
    _current_args = {**_current_args, **overrides}
    return get_config()


def get_current_args():
    """Return a copy of the current configuration arguments."""
    return dict(_current_args)


def get_config():
    """Return a Config instance built from current configuration arguments."""
    return Config(**_current_args)


def set_other_prompt(prompt_name: str, prompt: str = ""):
    """设置其他系统提示词相关配置。

    Args:
        prompt_name (str): 提示词名称，例如 "SKILL_PROMPT"。
        prompt (str): 所需提示词。
    """
    _other_prompts[prompt_name] = prompt


def get_system_prompt_config():
    """获取系统提示词相关配置。"""
    return dict(_other_prompts)


class Config():
    """ 配置类

    用于存储项目的配置信息，如 API 密钥、数据库连接信息等:
        - 系统路径相关配置
        - 系统提示词相关配置
        - 上下文窗口大小默认配置
        - 模型相关配置
    """
    def __init__(self, **kwargs):
        """ 初始化配置类

        Args:
            kwargs: 配置参数字典

        Returns:
            None
        """

        # 系统路径相关配置
            # Path.cwd() 返回的是 Path 对象，不是普通字符串。os.getcwd() 返回的是普通字符串。
            # WORKDIR：当前工作目录
            # TOOL_RESULT_DIR：工具调用结果保存目录
            # SKILL_DIR：技能目录
        if not kwargs:
            kwargs = get_current_args()

        WORKDIR = Path.cwd()
        self.path_config = {
            "project_path": WORKDIR,
            "tool_result_dir": WORKDIR / ".agents" / ".task_output" / "tool_results",
            "transcript_dir": WORKDIR / ".agents" / "transcripts",
            "skill_dir": WORKDIR / ".agents" / "skills",
        }

        # 系统提示词相关配置
        self.prompt_config = {
            "system_prompt": DEFAULT_SYSTEM_PROMPT,
            "sub_system_prompt": DEFAULT_SUB_SYSTEM_PROMPT,
        }

        # 上下文窗口大小默认配置
        self.CHARS_PER_TOKEN = kwargs.get("chars_per_token", 1)                     # 每个 token 大约 chars_per_token 个字符
        self.CTX_TOKENS = kwargs.get("ctx_tokens", 20480)                           # 总上下文窗口大小
        self.MAIN_OUTPUT_TOKENS = int(self.CTX_TOKENS * 0.25)                       # 主输出预算
        self.SUMMARY_OUTPUT_TOKENS = min(int(self.CTX_TOKENS * 0.10), kwargs.get("max_tokens", 2048)) # 摘要输出预算
        self.SAFETY_TOKENS = int(self.CTX_TOKENS * 0.10)                            # 安全余量
        self.MAX_INLINE_TOOL_RESULT_TOKENS = int(self.CTX_TOKENS * 0.10)                                # 单个工具调用输出结果触发值（0.1）
        self.MAIN_INPUT_BUDGET = self.CTX_TOKENS - self.MAIN_OUTPUT_TOKENS - self.SAFETY_TOKENS         # 主输入预算（0.65）
        self.SUMMARY_INPUT_BUDGET = self.CTX_TOKENS - self.SUMMARY_OUTPUT_TOKENS - self.SAFETY_TOKENS   # 触发摘要的输入预算（0.8）
        self.COMPACT_TRIGGER_TOKENS = int(self.MAIN_INPUT_BUDGET * 0.75)                                # 压缩触发阈值（0.4875）
        # self.content_config = {
        #     "chars_per_token": self.CHARS_PER_TOKEN,
        #     "ctx_tokens": self.CTX_TOKENS,
        #     "main_output_tokens": self.MAIN_OUTPUT_TOKENS,
        #     "summary_output_tokens": self.SUMMARY_OUTPUT_TOKENS,
        #     "safety_tokens": self.SAFETY_TOKENS,
        #     "max_inline_tool_result_tokens": self.MAX_INLINE_TOOL_RESULT_TOKENS,
        #     "main_input_budget": self.MAIN_INPUT_BUDGET,
        #     "summary_input_budget": self.SUMMARY_INPUT_BUDGET,
        #     "compact_trigger_tokens": self.COMPACT_TRIGGER_TOKENS,
        # }

        # 模型相关配置
        self.model_config = {
            "api": kwargs.get("api", "anthropic"),
            "model_url": kwargs.get("model_url", "http://localhost:8000"),
            "api_key": kwargs.get("api_key", "no-key"),
            "model_name": kwargs.get("model_name", "claude-fable-5"),
        }

    # —————— 获取路径相关配置 ——————
    def get_path_config(self, path_name: str):
        """ 获取路径相关配置

        Args:
            path_name (str): 路径名称，例如 "project_path"、"tool_result_dir"、"transcript_dir"、"skill_dir" 等。

        Returns:
            dict: 所需路径相关字典

        Raises:
            ValueError: 如果路径名称不存在。
        """
        if path_name not in self.path_config:
            raise ValueError(f"路径名称 {path_name} 不存在")
        return self.path_config[path_name]

    def get_project_path(self):
        """Get the project root path."""
        return self.get_path_config("project_path")

    # —————— 获取提示词相关配置 ——————
    def get_system_prompt(self):
        """ 获取系统提示词

        Returns:
            str: 系统提示词
        """
        other_prompts = "".join(get_system_prompt_config().values())

        return self.prompt_config["system_prompt"] + other_prompts

    def get_sub_system_prompt(self):
        """ 获取子智能体系统提示词

        Returns:
            str: 子智能体系统提示词
        """
        other_prompts = "".join(get_system_prompt_config().values())

        return self.prompt_config["sub_system_prompt"] + other_prompts

    # —————— 获取上下文窗口大小相关配置 ——————
    def get_content_length(self):
        """ 获取上下文窗口大小相关配置

        获取需要的上下文窗口大小配置的项目，例如 "CHARS_PER_TOKEN"、"CTX_TOKENS" 等。

        Returns:
            tokens_config (dict): 上下文窗口大小配置字典
        """
        tokens_config = {}
        for key in ["CHARS_PER_TOKEN",
                    "CTX_TOKENS",
                    "MAIN_OUTPUT_TOKENS",
                    "SUMMARY_OUTPUT_TOKENS",
                    "SAFETY_TOKENS",
                    "MAX_INLINE_TOOL_RESULT_TOKENS",
                    "MAIN_INPUT_BUDGET",
                    "SUMMARY_INPUT_BUDGET",
                    "COMPACT_TRIGGER_TOKENS"]:
            tokens_config[key] = getattr(self, key)

        return tokens_config

    # —————— 获取模型相关配置 ——————
    def get_model_config(self):
        """ 获取模型相关配置

        Returns:
            dict: 模型相关字典
        """
        return self.model_config
