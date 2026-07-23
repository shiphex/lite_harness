""" 工具处理程序。

该模块包含工具处理程序的实现，用于处理不同类型的工具调用。

Typical usage example:
    import tools
"""

from .powershell import run_powershell
from .file_option import run_read, run_write, run_edit, run_glob
from .todo_write import run_todo_write
from .subagent import spawn_subagent
from .load_skill import load_skill


# 初级工具列表
STANDARD_TOOLS_LIST = [
    {"name": "powershell", "description": "执行一个 PowerShell 命令。",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "read_file", "description": "读取文件内容。",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, 
                                                       "limit": {"type": "integer", 
                                                                 "description": "从文件开头读取的最大行数。默认值为 200。", 
                                                                 "default": 200}}, "required": ["path"]}},
    {"name": "write_file", "description": "将内容写入文件。",
    "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "edit_file", "description": "一次性替换文件中的指定文本。",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
    {"name": "glob", "description": "查找与 glob 模式匹配的文件。",
     "input_schema": {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]}},   
]


# 高级工具列表
ADVANCED_TOOLS_LIST = [
    # "todo_write"：要求模型传入：
    # {
    #     "todos": [
    #         {"content": "阅读项目结构", "status": "completed"},
    #         {"content": "定位报错原因", "status": "in_progress"},
    #         {"content": "修改代码并测试", "status": "pending"}
    #     ]
    # }
    {
        "name": "todo_write","description": "创建并管理当前编码会话的任务列表。",
        "input_schema": {
            "type": "object",
            "properties": {
                "todos":{
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string"},
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"]     # 枚举，任务状态，只能是 pending、in_progress、completed
                            }
                        },
                        "required": ["content", "status"]
                    }
                }
            },
            "required": ["todos"]
        }
    },
    {"name": "subagent", "description": "启动一个 subagent 来处理复杂的子任务，仅返回最终结果。当任务可以拆解成多个子任务时，为每一个子任务创建一个独立的 subagent。",
     "input_schema": {"type": "object", "properties": {"description": {"type": "string"}}, "required": ["description"]}},
    {"name": "load_skill", "description": "按名称加载 skill 的全部内容。",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}, 
]

TOOLS_LIST = STANDARD_TOOLS_LIST + ADVANCED_TOOLS_LIST


# 初级工具分发映射
STANDARD_TOOLS_HANDLERS = {
    "powershell":   run_powershell,
    "read_file":    run_read,
    "write_file":   run_write,
    "edit_file":    run_edit,
    "glob":         run_glob,
    "load_skill":   load_skill,
}

# 高级工具分发映射
ADVANCED_TOOLS_HANDLERS = {
    "todo_write":   run_todo_write,
    "subagent":     spawn_subagent,
}

TOOLS_HANDLERS = STANDARD_TOOLS_HANDLERS | ADVANCED_TOOLS_HANDLERS


# 工具调用函数
def call_tool(tool_name: str, tool_input: dict):
    """ 调用指定工具。

    Args:
        tool_name: 工具名称。
        tool_input: 工具输入参数。

    Returns:
        工具输出结果。
    """
    handler = TOOLS_HANDLERS.get(tool_name)
    return handler(**tool_input) if handler else f"Unknown: {tool_name}"