""" 记忆系统 Memory System  

本模块用于管理记忆文件，包括加载、提取、整理相关的记忆文件。

Typical usage example:
    load_memories(messages)
    extract_memories(messages)
    consolidate_memories()
"""
import time
import yaml
import re
import json
import api
import cli
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class MemoryMode(str, Enum):
    """ 记忆模式枚举类 """
    OFF = "off"
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"


@dataclass(frozen=True)
class MemoryPolicy:
    mode: MemoryMode = MemoryMode.OFF
    namespace: str = "default"

    @property
    def can_read(self) -> bool:
        """ 是否可以读取记忆文件 """
        return self.mode in (
            MemoryMode.READ_ONLY, 
            MemoryMode.READ_WRITE
        )

    @property
    def can_write(self) -> bool:
        """ 是否可以写入记忆文件 """
        return self.mode == MemoryMode.READ_WRITE


class MemoryManager:
    """ 记忆管理器类 """
    def __init__(self, root: Path, policy: MemoryPolicy):
        self.root = root
        self.policy = policy
        self.index_path = self.root / "MEMORY.md"

        if self.policy.can_write:
            self.root.mkdir(parents=True, exist_ok=True)

    def load(self, messages: list) -> str:
        return load_memories(self, messages = messages)

    def extract(self, messages: list):
        """ 从压缩前的快照中提取记忆 """
        extract_memories(self, messages = messages)

    def consolidate(self):
        """ 合并记忆 """
        consolidate_memories(self)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """ 解析 memory 的 frontmatter
    
    解析 memory.md 文件的 frontmatter 部分，返回 (meta, body)。 
    
    Args:
        text (str): 包含 frontmatter 的文本内容。
    
    Returns:
        tuple[dict, str]: 包含 frontmatter 元数据和 body 的元组。
            meta: 包含 frontmatter 元数据的字典。
            body: 包含 frontmatter 后的文本内容。
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


def extract_text(content) -> str:
    """ 从 messages content 块中提取文本。
    
    Args:
        content (list): 包含文本块的列表，每个块是一个字典，包含 "text" 键。
    
    Returns:
        str: 提取的文本内容，每个文本块之间用换行符分隔。
    """
    # 从 messages content 块中提取文本。
    if not isinstance(content, list):
        return str(content)
    return "\n".join(
        str(b.get("text", ""))
        if isinstance(b, dict) and b.get("type") == "text"
        else str(getattr(b, "text", ""))
        for b in content
        if (isinstance(b, dict) and b.get("type") == "text")
        or getattr(b, "type", "") == "text"
    )


# ═══════════════════════════════════════════════════════════
# 记忆系统 Memory System
# ═══════════════════════════════════════════════════════════

# ------------------------- 加载记忆 -------------------------

def read_memory_file(self, filename: str) -> str | None:
    """读取指定记忆文件的完整文本内容。

    Args:
        filename (str): 记忆文件名，文件应位于当前 namespace 的 memory 根目录下。

    Returns:
        str | None: 文件存在时返回其 UTF-8 文本内容；文件不存在时返回 None。
    """
    if not self.policy.can_read:
        return None

    path = self.root / filename
    
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def list_memory_files(self) -> list[dict]:
    """列出可用的记忆文件及其元数据。

    扫描当前 namespace 的 memory 根目录下的 Markdown 文件，解析 YAML frontmatter，并返回
    文件名、名称、描述、类型和正文等用于检索与加载的字段。

    Returns:
        list[dict]: 记忆文件信息列表。每个元素包含 filename、name、
            description、type 和 body 字段。
    """
    if not self.policy.can_read:
        return []
    
    result = []
    for f in sorted(self.root.glob("*.md")):
        if f.name == self.index_path.name or not f.is_file():
            continue

        raw = f.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(raw)

        result.append({
            "filename": f.name,
            "name": meta.get("name", f.stem),   # .stem 是文件名去掉扩展名
            "description": meta.get("description", ""),
            "type": meta.get("type", "user"),
            "body": body
        })
    return result


def select_relevant_memories(self, messages: list, max_items: int = 5) -> list[str]:
    """根据最近对话选择相关的记忆文件。

    优先调用 LLM 根据最近用户消息与记忆目录进行语义匹配；当 LLM 调用或
    解析失败时，回退到简单关键词匹配。

    Args:
        messages (list): 当前会话消息列表，元素通常包含 role 和 content 字段。
        max_items (int): 最多返回的记忆文件数量。

    Returns:
        list[str]: 被选中的记忆文件名列表。
    """
    # 加载全部的记忆文件
        # 为什么把加载记忆文件的代码放在这里？而不是在收集用户上下文信息后面？
        # 因为不存在记忆文件时，选择记忆文件就毫无意义，直接退出函数
    files = list_memory_files(self)
    if not files:
        return []

    # 收集用户最近的文本以获取上下文信息
    recent_texts = []
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            # 对应信息是列表时（工具调用结果）
            if isinstance(content, list):
                content = " ".join(
                    str(getattr(b, "text", "")) for b in content
                    if getattr(b, "type", None) == "text"
                )
            # 对应信息是普通文本时
            if isinstance(content, str):
                recent_texts.append(content)
            # 限制收集的文本数量(存在问题：当信息是列表时，解析出来的数据可能远超3条)
            if len(recent_texts) >= 3:
                break

    # 合并最近的文本
        # 存在的问题：截取的是最近三条的前2000个字符，按道理应该是最后2000个字符，才是最近的
    recent = " ".join(reversed(recent_texts))[:2000]
    # 滤除空字符串
    if not recent.strip():
        return []

    # 加载记忆文件，并将记忆文件的索引、名称/描述拼接成一个字符串，用于 LLM 匹配。
    catalog_lines = []
    for i, f in enumerate(files):
        catalog_lines.append(f"{i}: {f['name']} - {f['description']}")
    catalog = "\n".join(catalog_lines)

    # 调用 LLM 进行匹配
    prompt = (
        "根据最近的对话和下面的记忆目录，选择明显相关的记忆索引。" 
        "仅返回一个整数 JSON 数组，例如: [0, 3]。"
        "如果没有相关的记忆，则返回 []。\n\n"
        f"最近的对话: {recent}\n"
        f"记忆目录:\n{catalog}"
    )
    try:
        # 让 LLM 调用模型，获取记忆索引编号（JSON 数组格式）
        response = api.call_model(
            messages = [{"role": "user", "content": prompt}],
            model_pattern = "mini",
        )
        text = extract_text(response.content).strip()
        # 提取 JSON 数组，使用“？”非贪婪匹配，排配第一个 JSON 数组
            # 利用**正则表达式（Regular Expression）**在一段名为 text 的文本中，
            # 寻找并提取第一个被方括号 [...] 包裹的 JSON 数组。
        match = re.search(r'\[.*?\]', text, re.DOTALL)
        if match:
            indices = json.loads(match.group()) # match.group()把包裹着方括号的原始文本字符串拿出来，类型是 str
                                                # json.loads()负责把这个符合 JSON 规范的字符串，翻译成 Python 原生的数据结构。
            # 过滤出被选中的记忆文件的文件名
            selected = []
            for idx in indices:
                if isinstance(idx, int) and 0 <= idx < len(files):
                    selected.append(files[idx]["filename"])
                    # 限制选择的记忆文件数量
                    if len(selected) >= max_items:
                        break
            return selected
    except Exception:
        pass

    # 如果 LLM 调用失败，使用关键词匹配
        # 问题：这种匹配关键词的方式不适合中文（import jieba 分词）
    # 寻找出现次数大于三次的单词
    keywords = [w.lower() for w in recent.split() if len(w) > 3]
    selected = []
    for f in files:
        text = (f["name"] + " " + f["description"]).lower()
        if any(kw in text for kw in keywords):
            selected.append(f["filename"])
            if len(selected) >= max_items:
                break

    return selected


def load_memories(self, messages: list) -> str:
    """加载与当前会话相关的记忆内容。

    Args:
        messages (list): 当前会话消息列表。

    Returns:
        str: 使用 <relevant_memories> 标签包裹的记忆文本；没有相关记忆时返回空字符串。
    """
    if not self.policy.can_read:
        return ""

    selected_files = select_relevant_memories(self, messages)
    if not selected_files:
        return ""

    parts = ["<relevant_memories>"]
    for filename in selected_files:
        content = read_memory_file(self, filename)
        if content:
            parts.append(content)
    parts.append("</relevant_memories>")
    return "\n\n".join(parts)


# ------------------------- 提取记忆 -------------------------

def _rebuild_index(self):
    """根据当前记忆文件重建记忆索引文件。

    遍历当前 namespace 的 memory 根目录下的 Markdown 文件，提取名称和描述后写入
    当前 namespace 的 MEMORY.md 文件，供后续人工查看或系统检索。
    """
    lines = []
    for f in sorted(self.root.glob("*.md")):
        if f.name == self.index_path.name or not f.is_file():
            continue
        raw = f.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(raw)
        name = meta.get("name", f.stem)
        desc = meta.get("description", body.split("\n")[0][:80])
        lines.append(f"- [{name}]({f.name}) - {desc}")
    self.index_path.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")


def write_memory_file(self, name: str, mem_type: str, desc: str, body: str):
    """写入单条记忆并刷新索引（使用 YAML 格式存储记忆文件）。

    Args:
        name (str): 记忆名称，会被转换为文件名 slug。
        mem_type (str): 记忆类型，例如 user、feedback、project 或 reference。
        desc (str): 用于索引和匹配的单行描述。
        body (str): 记忆正文内容。

    Returns:
        pathlib.Path: 写入后的记忆文件路径。
    """
    if not self.policy.can_write:
        return None
    
    slug = name.lower().replace(" ", "-").replace("'", "-")
    path = self.root / f"{slug}.md"

    path.write_text(
        f"---\nname: {name}\ndescription: {desc}\ntype: {mem_type}\n---\n\nbody: {body}\n", encoding="utf-8"
    )
    _rebuild_index(self)
    return path


def extract_memories(self, messages: list):
    """从近期对话中提取新的长期记忆。

    将最近消息整理为对话文本，结合已有记忆摘要提示 LLM 提取新增记忆。
    提取结果必须是 JSON 数组，且每项包含 name、type、description、body 字段。

    Args:
        messages (list): 当前会话消息列表。

    Returns:
        str | None: 对话为空时返回空字符串；其他情况下主要通过写入文件产生副作用。
    """
    if not self.policy.can_write:
        return ""

    dialogue_parts = []
    # 从最新的10条消息中提取对话内容
        # 问题：如果该轮对话的消息远多于10条，导致记忆提取丢失。
    for msg in messages[-10:]:
        role = msg.get("role", "?")
        content = msg.get("content", "")
        if isinstance(content, list):
            content = extract_text(content)
        if isinstance(content, str) and content.strip():
            dialogue_parts.append(f"{role}: {content}")
    dialogue = "\n".join(dialogue_parts)

    # 排除空对话
    if not dialogue.strip():
        return ""

    # 检查已存在记忆文件避免重复记录
    existing_files = list_memory_files(self)
    existing_desc = "\n".join(f"- {m['name']} - {m['description']}" 
                              for m in existing_files) \
                              if existing_files else "(none)"

    # 调用大模型提取记忆
    prompt = (
        "从该对话中提取用户偏好、限制条件或项目信息。\n"
        "返回一个 JSON 数组。每个元素包含：{name, type, description, body}。\n"
        "- name: 简短的 kebab-case 标识符(例如 'user-preference-tabs')\n"
        "- type: 其中之一是 'user'（用户偏好）、'feedback'（指导）、"
        "'project'（项目事实）、'reference'（外部指针）。\n"
        "- description: 索引查找的单行摘要。\n"
        "- body: markdown 格式化记忆的详细内容。\n"
        "如果没有新的内容或现有记忆已涵盖的内容，则返回 []。\n\n"
        f"已存在记忆文件：\n{existing_desc}\n"
        f"对话内容：\n{dialogue[:4000]}"
    )
    try:
        # 让 LLM 调用模型，提取记忆内容
        response = api.call_model(
                    messages = [{"role": "user", "content": prompt}],
                    model_pattern = "mini",
                )
        text = extract_text(response.content).strip()
        if not text:
            return
        # 提取 JSON 文本段，使用“？”非贪婪匹配，排配第一个 JSON 文本段
            # 利用**正则表达式（Regular Expression）**在一段名为 text 的文本中，
            # 寻找并提取第一个被方括号 [...] 包裹的 JSON 文本段。
        match = re.search(r'\[.*\]', text, re.DOTALL)

        # 解析 JSON，排除空文本段
        if not match:
            cli.inform_system_info("\n[Memory: 提取失败] 模型未返回 JSON 数组")
            return
        items = json.loads(match.group())
        if not items:
            return

        count = 0
        for mem in items:
            name = mem.get("name", f"memory_{int(time.time())}")
            mem_type = mem.get("type", "user")
            desc = mem.get("description", "")
            body = mem.get("body", "")
            if desc and body:
                write_memory_file(self, name, mem_type, desc, body)
                count += 1
        if count:
            cli.inform_system_info(f"\n[Memory: 成功提取 {count} 条新记忆]")
    except Exception as e:
        cli.inform_system_info(f"\n[Memory: 提取失败] {e}")


# ------------------------- 整理记忆 -------------------------

CONSOLIDATE_THRESHOLD = 10
"""触发记忆整理的最小记忆文件数量。"""

# 整理记忆文件
    # 合并重复/过期的内存。当文件数量≥阈值时触发。
def consolidate_memories(self):
    """整理并合并已有记忆文件。

    当记忆文件数量达到 CONSOLIDATE_THRESHOLD 后，调用 LLM 合并重复内容、
    删除过期或冲突信息，并用整理后的结果重写记忆文件集合。
    """
    if not self.policy.can_write:
        return ""

    files = list_memory_files(self)
    if len(files) < CONSOLIDATE_THRESHOLD:
        return

    # 生成记忆目录(问题：只靠 \n\n 和 ## 来分隔不同记忆文件，可能会导致不同文件难以区分)
    catalog = "\n\n".join(
        f"## {f['filename']}\nname: {f['name']}\ndescription: {f['description']}\nbody: {f['body']}"
        for f in files
    )

    # 使用 LLM 整理记忆
    prompt = (
        "合并以下记忆文件。规则如下：\n"
        "1. 将重复内容合并为一条\n"
        "2. 删除过时、相互冲突的记忆信息\n"
        "3. 记忆信息总数控制在30条以内\n"
        "4. 优先保留用户的重要偏好设置\n"
        "返回一个 JSON array。每个元素包含：{name, type, description, body}。\n\n"
        f"{catalog[:16000]}"
    )
    try:
        response = api.call_model(
                    messages = [{"role": "user", "content": prompt}],
                    model_pattern = "summary",
                )
        text = extract_text(response.content).strip()
        # 提取 JSON 文本段，使用“？”非贪婪匹配，排配第一个 JSON 文本段
            # 利用**正则表达式（Regular Expression）**在一段名为 text 的文本中，
            # 寻找并提取第一个被方括号 [...] 包裹的 JSON 文本段。
        match = re.search(r'\[.*\]', text, re.DOTALL)
    
        # 解析 JSON，排除空文本段
        if not match:
            return
        items = json.loads(match.group())

        # 移除旧的记忆文件（但保留 MEMORY.md）
        for f in self.root.glob("*.md"):
            if f.name != "MEMORY.md":
                f.unlink()

        # 写入新记忆文件
        for mem in items:
            name = mem.get("name", f"memory_{int(time.time())}")
            mem_type = mem.get("type", "user")
            desc = mem.get("description", "")
            body = mem.get("body", "")
            if desc and body:
                write_memory_file(self, name, mem_type, desc, body)

        cli.inform_system_info(f"\n[Memory: 成功整理 {len(files)} → {len(items)} 条记忆]")

    except Exception:
        pass
