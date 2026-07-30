"""系统提示词加载与拼装工具。

本模块负责读取已注册的 skill 目录信息和记忆索引，并将它们拼接到
系统提示词中。调用方需要在模块作用域提供以下对象：
    SKILL_REGISTRY: skill 注册表，值包含 name 和 description 字段。
    MEMORY_INDEX: 记忆索引文件路径，通常为 pathlib.Path。
    WORKDIR: 当前项目工作目录。

Typical usage example:
    build_system()
"""

import config

try:
    from tools.load_skill import SKILL_REGISTRY
except Exception:
    SKILL_REGISTRY = {}


WORKDIR = config.Config().get_project_path()
"""当前项目工作目录。"""

MEMORY_INDEX = config.Config().get_path_config("memory_index")
"""记忆索引文件路径。"""

# ═══════════════════════════════════════════════════════════
# 加载系统提示词
# ═══════════════════════════════════════════════════════════

# 获取 skill 列表
def list_skill() -> str:
    """List all skills (name + one-line description).

    从 SKILL_REGISTRY 中读取 skill 名称和单行描述，并格式化为可直接
    写入系统提示词的 Markdown 列表。

    Returns:
        str: skill 列表文本；没有发现 skill 时返回默认提示。
    """
    if not SKILL_REGISTRY:
        return "(没有发现 skill。)"
    # 为避免外层""与内层的被错误匹配，内部使用''
    return "\n".join(f"- **{s['name']}**: {s['description']}" 
                     for s in SKILL_REGISTRY.values())


# 读取记忆索引
def read_memory_index():
    """读取记忆索引文件内容。

    Returns:
        str: 去除首尾空白后的记忆索引文本；文件不存在或内容为空时返回空字符串。
    """
    if not MEMORY_INDEX.exists():
        return ""
    text = MEMORY_INDEX.read_text(encoding="utf-8").strip()
    return text if text else ""


# 构建系统提示词
def build_system() -> str:
    """构建完整系统提示词。

    系统提示词包含当前工作目录、运行环境、任务规划要求、可用 skill
    目录，以及可选的记忆索引片段。

    Returns:
        str: 拼装后的系统提示词。
    """
    catalog = list_skill()
    index = read_memory_index()
    memories_section = f"\n\nMemories available:\n{index}" if index else ""

    return (f"你是一个编码助手，位于 {WORKDIR}，当前系统环境是 Windows。使用 PowerShell 解决任务。行动，无需解释。"
          f"在开始任何多步骤任务之前，请使用 todo_write 来规划您的步骤。"
          f"当前可用的 skill 有：{catalog}"
          f"对于复杂的子问题，可以使用任务工具生成子智能体。"
          f"{memories_section}"
)
