"""系统提示词加载与拼装工具。

本模块负责读取已注册的 skill 目录信息和记忆索引，并将它们拼接到
系统提示词中。调用方需要在模块作用域提供以下对象：
    SKILL_REGISTRY: skill 注册表，值包含 name 和 description 字段。
    MEMORY_INDEX: 记忆索引文件路径，通常为 pathlib.Path。
    WORKDIR: 当前项目工作目录。

Typical usage example:
    build_system()
"""

import json
import config
from pathlib import Path
from observability.logger import get_logger
logger = get_logger(__name__)

try:
    from tools.load_skill import SKILL_REGISTRY
except Exception:
    SKILL_REGISTRY = {}

try:
    from tools.tool_handler import TOOLS_LIST, TOOLS_HANDLERS
except Exception:
    TOOLS_LIST = []
    TOOLS_HANDLERS = {}



WORKDIR = config.Config().get_project_path()
"""当前项目工作目录。"""

MEMORY_INDEX = config.Config().get_path_config("memory_index")
"""记忆索引文件路径。"""


class PromptBuilder:

    def __init__(self):
        self._last_context_key = None
        self._last_prompt = None

    def build(self, 
              runtime, 
        ) -> str:

        context = update_context(
            runtime.state.context,
            memory_index=runtime.memory.index_path,
        )
        runtime.state.context = context
        system_prompt = self.get_system_prompt(runtime, context)

        return system_prompt

    # 获得系统提示词
    def get_system_prompt(self, runtime, context: dict) -> str:
        """获取当前上下文对应的系统提示词。

        缓存键由 ``context`` 的稳定 JSON 表示生成。因此，键顺序不同但内容
        等价的字典会复用同一份提示词；JSON 原生不支持的值会通过 ``str`` 转换。

        Args:
            context (dict): 用于组装提示词的运行时上下文。

        Returns:
            str: 上下文未变化时返回缓存提示词，否则返回重新组装的提示词。
        """

        # 将 Python 对象序列化为 JSON 字符串。
        # sort_keys=True: 字典的键强制按字母升序排序后输出 JSON。
        # ensure_ascii=False: 直接输出原始中文 / 特殊字符，不转义成 Unicode 转义字符。
        # default=str: 处理 JSON 原生不支持序列化的对象，如 None、datetime 等。
        runtime_key = {
            "workspace": str(runtime.paths.workspace),
            "tools": runtime.policy.tools_list,
        }
        key = json.dumps(
            {"runtime": runtime_key, "context": context},
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )
        if key == self._last_context_key and self._last_prompt:
            logger.debug(
                "calling model session=%s agent=%s turn=%d "
                "[cache init]系统提示词未变化",
                runtime.session_id,
                runtime.agent_id,
                runtime.state.turn_count,
            )
            return self._last_prompt

        # 更新系统提示词
        self._last_context_key = key
        self._last_prompt = assemble_system_prompt(runtime, context)

        # 打印加载的段落
        loaded = ["identity", "tools", "workspace"]
        if context.get("memories"):
            loaded.append("memory")
        logger.debug(
            "calling model session=%s agent=%s turn=%d "
            "system prompt assembled: sections=%s",
            runtime.session_id,
            runtime.agent_id,
            runtime.state.turn_count,
            loaded,
        )
        return self._last_prompt
 


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
def read_memory_index(memory_index: Path | None = None):
    """读取记忆索引文件内容。

    Returns:
        str: 去除首尾空白后的记忆索引文本；文件不存在或内容为空时返回空字符串。
    """
    index_path = memory_index or MEMORY_INDEX
    if not index_path.is_file():
        return ""
    text = index_path.read_text(encoding="utf-8").strip()
    return text if text else ""


# 构建系统提示词（已经废弃的半静态加载）
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


# ═══════════════════════════════════════════════════════════
# 构建系统提示词
# ═══════════════════════════════════════════════════════════

PROMPT_SECTIONS = {
    "identity": "当前系统环境是 Windows。使用 PowerShell 解决任务。行动，无需解释。",
    "tools": f"当前可用的 tool 有：{', '.join([tool['name'] for tool in TOOLS_LIST])}",
    "workspace": f"当前工作目录是 {WORKDIR}",
    "skill": f"当前可用的 skill 有：{list_skill()}",
    "memory": "相关记忆内容将在下方插入（如有）。"
}


# 组装系统提示词
def assemble_system_prompt(runtime, context: dict) -> str:
    """根据静态片段和运行时上下文组装系统提示词。

    Args:
        context (dict): 运行时上下文。当 ``memories`` 存在且非空时，
            会作为记忆片段追加到提示词末尾。

    Returns:
        str: 使用空行分隔的完整系统提示词文本。
    """
    sections = []

    if runtime.policy.prompt:
        sections.append(runtime.policy.prompt)

    sections.append(PROMPT_SECTIONS["identity"])
    sections.append(f"当前可用的 tool 有：{', '.join([tool['name'] for tool in runtime.policy.tools_list])}")
    sections.append(f"当前工作目录是 {runtime.paths.workspace}")
    sections.append(PROMPT_SECTIONS["skill"])
    sections.append(PROMPT_SECTIONS["memory"])

    memories = context.get("memories", "")
    if memories:
        sections.append(f"相关记忆：\n{memories}")

    return "\n\n".join(sections)


# 更新上下文
def update_context(
    context: dict,
    memory_index: Path | None = None,
) -> dict:
    """构建提示词组装器需要的运行时上下文。

    Args:
        context (dict): 现有会话上下文。函数不会修改原字典。
        memory_index (Path | None): 可选的记忆索引路径。

    Returns:
        dict: 保留已有上下文并更新记忆索引内容。
    """
    memories = read_memory_index(memory_index)
    return {
        **context,
        "memories": memories,
    }
