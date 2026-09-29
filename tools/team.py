"""仅向 MasterAgent 暴露的 Agent Team 工具绑定。"""

from dataclasses import asdict
import json

from team.contracts import TeamError
from team.runtime import TeamRuntime
from tools.task_system import TaskError
from tools.tool_class import ToolContext


TEAM_MASTER_TOOLS = [
    {
        "name": "spawn_teammate",
        "description": "创建一个空闲 TeamAgent；spawn 本身不会启动模型执行。",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "pattern": "^[A-Za-z][A-Za-z0-9_-]{0,31}$",
                },
            },
            "required": ["agent_name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "create_team_task",
        "description": "在当前团队创建任务。",
        "input_schema": {
            "type": "object",
            "properties": {"subject": {"type": "string"}, "description": {"type": "string"}},
            "required": ["subject"], "additionalProperties": False,
        },
    },
    {
        "name": "list_team_tasks",
        "description": "列出当前团队任务看板。",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_team_task",
        "description": "读取当前团队的一项任务。",
        "input_schema": {
            "type": "object", "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"], "additionalProperties": False,
        },
    },
    *[
        {
            "name": name,
            "description": description,
            "input_schema": {
                "type": "object",
                "properties": {"task_id": {"type": "string"}, "agent_id": {"type": "string"}},
                "required": ["task_id", "agent_id"], "additionalProperties": False,
            },
        }
        for name, description in (
            ("assign_team_task", "将团队任务分配给指定 TeamAgent 并同步执行一轮。"),
            ("resume_team_task", "让原 owner 显式续跑或修复团队任务状态。"),
        )
    ],
]


def bind_team_handlers(team_runtime: TeamRuntime) -> dict:
    """把 Master tool handler 绑定到当前 session 的 TeamRuntime。"""

    def spawn_teammate(context: ToolContext, agent_name: str) -> str:
        try:
            member = team_runtime.coordinator.spawn_teammate(
                parent_runtime=context.runtime,
                agent_name=agent_name,
            )
        except TeamError as exc:
            return f"Team error: {exc}"
        return json.dumps(asdict(member), ensure_ascii=False)

    def check_master(context: ToolContext) -> None:
        if getattr(context.runtime, "session_id", None) != team_runtime.session_id:
            raise TeamError("Master runtime 不属于当前 TeamRuntime session")

    def task_result(context: ToolContext, operation, *args, **kwargs) -> str:
        try:
            check_master(context)
            return json.dumps(operation(*args, **kwargs), ensure_ascii=False)
        except (TeamError, TaskError) as exc:
            return f"Team error [{type(exc).__name__}]: {exc}"

    def create_team_task(
        context: ToolContext, subject: str, description: str = ""
    ) -> str:
        def operation():
            return {
                "status": "created",
                "task": asdict(team_runtime.coordinator.create_task(subject, description)),
            }
        return task_result(context, operation)

    def list_team_tasks(context: ToolContext) -> str:
        return task_result(
            context,
            lambda: {"tasks": [asdict(task) for task in team_runtime.coordinator.list_tasks()]},
        )

    def get_team_task(context: ToolContext, task_id: str) -> str:
        return task_result(
            context,
            lambda: {"task": asdict(team_runtime.coordinator.get_task(task_id))},
        )

    def assign_team_task(context: ToolContext, task_id: str, agent_id: str) -> str:
        return task_result(
            context,
            team_runtime.coordinator.assign_task,
            task_id,
            agent_id,
        )

    def resume_team_task(context: ToolContext, task_id: str, agent_id: str) -> str:
        return task_result(
            context,
            team_runtime.coordinator.resume_task,
            task_id,
            agent_id,
        )

    return {
        "spawn_teammate": spawn_teammate,
        "create_team_task": create_team_task,
        "list_team_tasks": list_team_tasks,
        "get_team_task": get_team_task,
        "assign_team_task": assign_team_task,
        "resume_team_task": resume_team_task,
    }
