""" 文件操作工具. 

用于文件的读、写、修改操作。

Typical usage example:
    import tools.file_option as file_option
    file_option.run_read("config/config.py")
    file_option.run_write("config/config.py", "new content")
    file_option.run_edit("config/config.py", "old content", "new content")
"""

from pathlib import Path
import config
from .tool_class import ToolContext

# 获取项目根目录
WORKDIR = config.Config().get_path_config("project_path")


def safe_path(p: str) -> Path:
    """ 安全路径转换工具. 
    
    该函数用于把模型传进来的相对路径 p，转换成一个规范化后的绝对路径。
    它会确保路径在工作目录下，避免路径遍历攻击。
    
    Args:
        p (str): 相对路径，例如 "config/config.py"
    
    Returns:
        Path: 规范化后的绝对路径，例如 "D:/Workplace/project/config/config.py"
    
    Raises:
        ValueError: 如果路径不在工作目录下
    """

    # 解析路径，确保它在工作目录下
        # windows 系统下，路径分隔符是反斜杠 \，但 Python 的 Windows path flavor 能识别这种写法 
    path = (WORKDIR / p).resolve()      # pathlib 重载过的路径拼接运算符，.resolve() 会把路径变成绝对路径
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Error: 路径 {p} 不在工作目录 {WORKDIR} 下")
    return path


def run_read(context: ToolContext, path: str, limit: int = 200) -> str:   # | None = None 表示 limit 可以是 None，也可以是 int 类型的(联合类型)
    """ 读取文件内容工具. 
    
    该函数用于读取文件内容，返回文件内容的前 limit 行。
    如果文件为空，返回 "文件为空：{path}（0 字节）"。
    如果文件内容超过 limit 行，返回 "文件内容超过 limit 行，... 还有 {len(lines) - limit} 行"。
    
    Args:
        path (str): 相对路径，例如 "config/config.py"
        limit (int, optional): 读取的行数限制，默认值为 200。

    Returns:
        str: 文件内容的前 limit 行，或 "文件为空：{path}（0 字节）" 或 "文件内容超过 limit 行，... 还有 {len(lines) - limit} 行"

    Raises:
        ValueError: 如果路径不在工作目录下
    """

    try:
        lines = safe_path(path).read_text(encoding="utf-8").splitlines()    # 读取文件内容并按行分割

        if not lines:
            return f"文件为空：{path}（0 字节）"

        if limit and len(lines) > limit:
            lines = lines[:limit] + [f"... 还有 {len(lines) - limit} 行"]
        return "\n".join(lines)     # 在两个相邻元素中插入 \n 换行符
    except Exception as e:
        return f"Error: 读取文件 {path} 失败：{e}"


def run_write(context: ToolContext, path: str, content: str) -> str:
    """ 写入文件内容工具. 

    该函数用于写入文件内容。
    如果文件不存在，会创建一个新的文件。
    如果文件已存在，会覆盖文件内容。
    写入时会自动创建必要的父目录。
    
    Args:
        path (str): 相对路径，例如 "config/config.py"
        content (str): 要写入的文本内容
    
    Returns:
        str: 写入成功信息，例如 "写入 100 字符到 config/config.py 成功"
    
    Raises:
        ValueError: 如果路径不在工作目录下
    """
    try:
        file_path = safe_path(path)
        # 确保父目录存在，不存在则创建
            # exist_ok=True 表示如果目录已存在，不会抛出异常
            # parents=True 表示创建所有必要的父目录
        file_path.parent.mkdir(parents=True, exist_ok=True) 
        file_path.write_text(content, encoding="utf-8")
        return f"写入 {len(content)} 字符到 {path} 成功"
    except Exception as e:
        return f"Error: 写入文件 {path} 失败：{e}"


# edit_file 工具执行
def run_edit(context: ToolContext, path: str, old_text: str, new_text: str) -> str:
    """ 编辑文件内容工具. 

    该函数用于编辑文件内容。
    如果文件不存在，会返回 "Error: 文件 {path} 不存在"。
    如果文件内容中不存在 old_text，会返回 "Error: 文件 {path} 中不存在相关文本，无法替换"。
    
    Args:
        path (str): 相对路径，例如 "config/config.py"
        old_text (str): 要替换的旧文本
        new_text (str): 要替换的新文本
    
    Returns:
        str: 编辑成功信息，例如 "编辑文件 config/config.py 成功"
    
    Raises:
        ValueError: 如果路径不在工作目录下
    """
    try:
        file_path = safe_path(path)
        text = file_path.read_text(encoding="utf-8")
        if old_text not in text:
            return f"Error: 文件 {path} 中不存在相关文本，无法替换。"
        file_path.write_text(text.replace(old_text, new_text), encoding="utf-8")
        return f"编辑文件 {path} 成功"
    except Exception as e:
        return f"编辑文件 {path} 失败：{e}"


def run_glob(context: ToolContext, pattern: str) -> str:
    """ 搜索文件工具. 

    该函数用于在当前工作目录 WORKDIR 下面查找符合通配符模式的文件。
    如果没有匹配的文件，返回 "(no matches)"。
    如果有匹配的文件，返回符合通配符模式的文件路径列表，每个路径占一行。
    
    Args:
        pattern (str): 通配符模式，例如 "*.txt" 或 "**/*.txt"
    
    Returns:
        str: 符合通配符模式的文件路径列表，每个路径占一行
    
    Raises:
        ValueError: 如果路径不在工作目录下
    """
    import glob as g
    try:
        results = []
        # 返回匹配 pattern 的路径列表，路径为相对路径
            # 若要让检索递归，需要在模式中添加 recursive=True，并使用例如：**/*.txt
        for match in g.glob(pattern, root_dir = str(WORKDIR)):
            # 转换为绝对路径，并检查是否在工作目录下
            if (WORKDIR / match).resolve().is_relative_to(WORKDIR):
                # 如果在工作目录下，将相对路径添加到结果列表
                results.append(match)
        return "\n".join(results) if results else "(no matches)"
    except Exception as e:
        return f"Error: {e}"
