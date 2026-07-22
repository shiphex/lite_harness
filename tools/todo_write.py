""" todo_write 工具。

让模型在执行任务前，先使用 todo_write 来规划任务。
任务规划后，模型会根据任务规划，执行任务。
任务执行完成后，模型会根据任务规划，更新任务状态。
任务状态包括：pending 待办, in_progress 进行中, completed 已完成。

Typical usage example:
    from tools.todo_write import run_todo_write
    todos = run_todo_write(todos)
"""

import ast
import json
import cli


# reminder 机制
def _normalize_todos(todos):
    """ 校式化任务列表。

    该函数用于校验任务列表是否符合要求。
    如果任务列表是字符串，会尝试解析为列表。
    如果任务列表不是列表，会返回报错。
    如果任务列表中的每个元素不是字典，或包含 content 和 status 字段，会返回报错。
    如果任务列表中的每个元素的状态不是 pending, in_progress, completed 中的一个，会返回报错。

    Args:
        todos (list): 任务列表，每个任务是一个字典，包含 content 和 status 字段。
    
    Returns:
        tuple: 包含格式化后的任务列表 todos 和 None（成功）或错误信息（失败）。
    Raises:
        ValueError: 如果 todos 不是字符串或列表。
    """

    # 若 todos 是一个字符串，尝试解析为列表
    if isinstance(todos, str):
        try:
            todos = json.loads(todos)
        # 捕获 JSON 解析错误
        except json.JSONDecodeError:  
            try: 
                todos = ast.literal_eval(todos) # 安全地把字符串还原成 Python 对象(列表 / 字典)
            except (ValueError, SyntaxError):
                return None, "Error: 无法解析 todos 为列表。"
    
    # 若 todos 不是列表，返回报错
    if not isinstance(todos, list):
        return None, "Error: todos 必须是列表类型。"
    
    # 遍历 todos 列表，检查每个元素是否是一个字典，且包含 content 和 status 字段
    for i, t in enumerate(todos):   # 遍历todos序列，同时拿到索引i和对应元素t
        if not isinstance(t, dict):
            return None, f"Error: todos[{i}] 必须是一个对象类型。"
        if "content" not in t or "status" not in t:
            return None, f"Error: todos[{i}] 必须包含 content 和 status 字段。"
        if t["status"] not in ("pending", "in_progress", "completed"):
            return None, f"Error: todos[{i}] 的状态“{t['status']}”无效。"

    return todos, None


# todo_write 工具执行
    # 任务状态：pending 待办, in_progress 进行中, completed 已完成
def run_todo_write(todos: list) -> str:
    """ 设计任务规划。

    该函数用于设计任务规划。
    任务规划后，模型会根据任务规划，执行任务。
    任务执行完成后，模型会根据任务规划，更新任务状态。
    
    Args:
        todos (list): 任务列表，每个任务是一个字典，包含 content 和 status 字段。
    
    """

    global CURRENT_TODOS

    # 校验 todos 是否为列表
    todos, error = _normalize_todos(todos)
    if error:
        return error
    
    # 格式化输出
    CURRENT_TODOS = todos
    lines = ["\033[33m## Current Tasks\033[0m"]
    for t in CURRENT_TODOS:
        icon = {"pending": " ", "in_progress": "\033[36m▸\033[0m", "completed": "\033[32m✓\033[0m"}[t["status"]]   # 把整个大字典写在方括号前面，直接根据键取值
        lines.append(f"    [{icon}] {t['content']}")
    cli.put_agent_output("\n".join(lines))     # 打印格式化后的任务列表，在每个任务间添加换行符

    return f"更新 {len(CURRENT_TODOS)} 个任务。"