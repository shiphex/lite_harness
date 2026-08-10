""" 文件落盘存储

"""

from pathlib import Path
import json
import time


class ArtifactStore:
    """ 文件落盘存储类

    用于存储和检索文件，支持 JSON 格式。
    """
    def __init__(self, 
                 tool_result_dir: Path, 
                 transcript_dir: Path,
    ):
        self.tool_result_dir = tool_result_dir
        self.transcript_dir = transcript_dir


def persist_large_output(self, 
                         tool_use_id: str, 
                         output: str, 
                         threshold_chars: int) -> str:
    """ 保存大的输出到磁盘
    
    Args:
        tool_use_id (str): 工具调用 ID。
        output (str): 要保存的大的输出。
    
    Returns:
        str: 包含完整输出所在路径和预览的字符串。
    """
    if len(output) <= threshold_chars:
        return output
    
    self.tool_result_dir.mkdir(parents = True, exist_ok = True)
    path = self.tool_result_dir / f"{tool_use_id}.txt"
    if not path.exists():
        path.write_text(output, encoding = "utf-8")

    return f"<persisted-output>\n完整输出所在路径: {path}\n预览:\n{output[:200]}\n</persisted-output>"


def write_transcript(self, messages: list) -> Path:
    """ 将聊天记录写入到一个文件中
    
    该函数用于将聊天记录写入到一个文件中，
    每个消息占一行，消息之间用换行符隔开。
    
    Args:
        messages (list): 聊天记录列表，每个元素是一个字典，包含 role 和 content 字段。
    
    Returns:
        path (Path): 写入的文件路径。
    """
    

    self.transcript_dir.mkdir(parents = True, exist_ok = True)
    path = self.transcript_dir / f"transcript_{int(time.time())}.txt"
    with path.open("w", encoding = "utf-8") as f:
        for msg in messages:
            f.write(json.dumps(msg, default = str) + "\n")

    return path