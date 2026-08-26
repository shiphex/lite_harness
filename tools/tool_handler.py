""" 工具处理程序。

该模块包含工具处理程序的实现，用于处理不同类型的工具调用。

Typical usage example:
    import tools
"""

from .powershell import run_powershell, run_bash
from .file_option import run_read, run_write, run_edit, run_glob
from .todo_write import run_todo_write
from .subagent import run_subagent
from .load_skill import load_skill
from .tool_class import ToolContext
from .task_system import run_create_task, run_update_task, run_list_tasks, run_get_task, run_claim_task, run_complete_task


class ToolExecutor:
    def __init__(self, registry: dict, allowed_tools: list, workspace):
        self.registry = registry
        self.allowed_tools = {
            tool["name"] for tool in allowed_tools
        }
        self.workspace = workspace

    def execute(self, context: ToolContext, name: str, args: dict):
        if name not in self.allowed_tools:
            raise PermissionError(f"Tool not allowed: {name}")

        handler = self.registry.get(name)
        return handler(context, **args) if handler else f"Unknown: {name}"
       

# 初级工具列表
STANDARD_TOOLS_LIST = [
    {"name": "bash", "description": "执行一个命令行操作，若指定在后台运行，则返回任务 ID，否则返回命令执行结果。",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}, "run_in_background": {"type": "boolean"}}, "required": ["command"]}},
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
    {"name": "load_skill", "description": "按名称加载 skill 的全部内容。",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}, 
    {"name": "create_task", "description": "创建任务并返回其runtime-generated ID。",
     "input_schema": {"type": "object", 
                      "properties": {"subject": {"type": "string"}, 
                                     "description": {"type": "string"}}, 
                      "required": ["subject"], 
                      "additionalProperties": False}}, 
    {"name": "update_task", "description": "使用 create_task 返回的 ID 添加依赖项。",
     "input_schema": {"type": "object", 
                      "properties": {"task_id": {"type": "string", "pattern": "^task_[0-9a-f]{8}$"}, 
                                     "addBlockedBy": {"type": "array", 
                                                      "items": {"type": "string", "pattern": "^task_[0-9a-f]{8}$"}, 
                                                      "minItems": 1}}, 
                      "required": ["task_id", "addBlockedBy"], "additionalProperties": False}},
    {"name": "list_tasks", "description": "列出任务及其状态、负责人和依赖关系。",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_task", "description": "通过任务ID获取任务。",
     "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}},
    {"name": "claim_task", "description": "认领一项待处理任务，该任务的依赖项已全部完成。",
     "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}},
    {"name": "complete_task", "description": "完成 agent 提出的任务。",
     "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}},
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
    {"name": "compact", "description": "总结早期聊天记录以此释放上下文空间。",
     "input_schema": {"type": "object", "properties": {"focus": {"type": "string"}}}},
]

TOOLS_LIST = STANDARD_TOOLS_LIST + ADVANCED_TOOLS_LIST


# 初级工具分发映射
STANDARD_TOOLS_HANDLERS = {
    # "powershell":   run_powershell,
    "bash":         run_bash,
    "read_file":    run_read,
    "write_file":   run_write,
    "edit_file":    run_edit,
    "glob":         run_glob,
    "load_skill":   load_skill,
    "create_task":  run_create_task,
    "update_task":  run_update_task,
    "list_tasks":   run_list_tasks,
    "get_task":     run_get_task,
    "claim_task":   run_claim_task,
    "complete_task": run_complete_task,
}

# 高级工具分发映射
ADVANCED_TOOLS_HANDLERS = {
    "todo_write":   run_todo_write,
    "subagent":     run_subagent,
}

TOOLS_HANDLERS = STANDARD_TOOLS_HANDLERS | ADVANCED_TOOLS_HANDLERS
