""" 加载 skill 工具。

该 module 用于扫描、解析、加载 skills/ 目录下的 skill 工具。

Typical usage example:
    import tools.load_skill as load_skill

    load_skill.SKILL_REGISTRY
"""

from pathlib import Path
import yaml


WORKDIR = Path.cwd()
SKILL_DIR = WORKDIR / ".agents" / "skills"
# skill 注册表
SKILL_REGISTRY: dict[str, dict] = {}

# ═══════════════════════════════════════════════════════════
# skill 加载函数
# ═══════════════════════════════════════════════════════════

# 解析 skill 的 frontmatter
    # 解析 YAML frontmatter 格式的 SKILL.md 说明，返回 (meta, body)。
def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """ 解析 skill 的 frontmatter

    该函数用于解析 skill 的 frontmatter，返回 (meta, body)。

    Args:
        text (str): skill 的 frontmatter 内容，例如 "---\nname: skill_name\nndescription: skill_description\n---\nbody content"
    
    Returns:
        tuple[dict, str]: 包含 meta 和 body 的元组，例如 ({'name': 'skill_name', 'description': 'skill_description'}, 'body content')
    
    """

    # 检查是否以 "--- 开头
    if not text.startswith("---"):
        return {}, text
    
    # 将 SKILL.md 以 "---" 分割为 3 部分：""、frontmatter、body
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        meta = {}

    return meta, parts[2].strip()


# 检索 skill 注册表
    # 扫描 skills/ 目录，用名称/描述/内容填充 SKILL_REGISTRY。
def _scan_skill():
    """ 扫描 skill 注册表

    该函数用于扫描 skills/ 目录，用名称/描述/内容填充 SKILL_REGISTRY。

    Returns:
        None
    """

    # 检查路径是否存在
    if not SKILL_DIR.exists():
        return
    for d in sorted(SKILL_DIR.iterdir()):
        if not d.is_dir():
            continue
        manifest = d / "SKILL.md"
        if manifest.exists():
            raw = manifest.read_text(encoding="utf-8")
            meta, body = _parse_frontmatter(raw)
            name = meta.get("name", d.name)
            desc = meta.get("description", raw.split("\n")[0].lstrip("#").strip())      # 把字符串按照换行符\n切分成列表，列表第 0 项 [0] 代表取第一行文本。
            SKILL_REGISTRY[name] = {"name": name, "description": desc, "content": raw}

# 执行扫描 skill 注册表
_scan_skill()


# 获取 skill 列表
def list_skill() -> str:
    """ 获取 skill 列表

    该函数用于获取所有 skill 的名称和描述，返回一个格式化的字符串。

    Returns:
        str: 格式化的 skill 列表，例如 "- **skill_name**: skill_description\n- **skill_name2**: skill_description2\n...
    """
    if not SKILL_REGISTRY:
        return "(没有发现 skill。)"
    return "\n".join(f"- **{s['name']}**: {s['description']}" for s in SKILL_REGISTRY.values())     # 为避免外层""与内层的被错误匹配，内部使用''


def build_system() -> str:
    """ 构建系统提示词

    该函数用于构建系统提示词，包含所有 skill 的名称和描述。
    
    Returns:
        str: 系统提示词。
    """

    catalog = list_skill()

    return (f"你是一个编码助手，位于 {WORKDIR}，当前系统环境是 Windows。使用 PowerShell 解决任务。行动，无需解释。"
          f"在开始任何多步骤任务之前，请使用 todo_write 来规划您的步骤。"
          f"当前可用的 skill 有：{catalog}"
          f"对于复杂的子问题，可以使用任务工具生成子智能体。"
)


# 加载 skill 工具执行
def load_skill(name: str) -> str:
    """ 加载 skill 工具执行

    该函数用于加载指定 skill 的全部内容。

    Args:
        name (str): skill 的名称。

    Returns:
        str: skill 的全部内容。
    """
    skill = SKILL_REGISTRY.get(name)
    if not skill:
        return f"未找到 skill {name}。"
    return skill["content"]