"""只为所属 TeamAgent 绑定的团队任务工具。"""

from dataclasses import asdict
import json
from typing import Callable

from tools.task_system import (
    TaskError,
    TaskStore,
    complete_task_strict,
    create_task,
    load_task,
    update_task,
)
from tools.tool_class import ToolContext

from .agent import TeamAgent
from .contracts import MessageUnavailableError, TeamError
from .registry import MemberRegistry


TEAM_AGENT_TASK_TOOLS = [
    {
        "name": "get_team_task",
        "description": "读取当前团队的一项任务。",
        "input_schema": {
            "type": "object", "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"], "additionalProperties": False,
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
        "name": "update_team_task",
        "description": "为当前团队的待处理任务添加依赖。",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "addBlockedBy": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            },
            "required": ["task_id", "addBlockedBy"], "additionalProperties": False,
        },
    },
    {
        "name": "complete_team_task",
        "description": "完成当前分配给自己的团队任务。",
        "input_schema": {
            "type": "object", "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"], "additionalProperties": False,
        },
    },
]


def bind_task_handlers(
    get_agent: Callable[[str], TeamAgent],
    registry: MemberRegistry,
    store: TaskStore,
) -> dict:
    def current_agent(context: ToolContext) -> TeamAgent:
        runtime = context.runtime
        agent_id = getattr(runtime, "agent_id", None)
        if not isinstance(agent_id, str):
            raise MessageUnavailableError("调用方没有有效的 TeamAgent identity")
        agent = get_agent(agent_id)
        if agent.runtime is not runtime:
            raise MessageUnavailableError("调用方 runtime 与 TeamAgent 不匹配")
        return agent

    def failure(exc: Exception) -> str:
        return f"Team error [{type(exc).__name__}]: {exc}"

    def get_team_task(context: ToolContext, task_id: str) -> str:
        try:
            current_agent(context)
            task = load_task(task_id, store=store)
            return json.dumps({"task": asdict(task)}, ensure_ascii=False)
        except (TeamError, TaskError) as exc:
            return failure(exc)

    def create_team_task(
        context: ToolContext, subject: str, description: str = ""
    ) -> str:
        try:
            current_agent(context)
            task = create_task(subject, description, store=store)
            return json.dumps({"status": "created", "task": asdict(task)}, ensure_ascii=False)
        except (TeamError, TaskError) as exc:
            return failure(exc)

    def update_team_task(
        context: ToolContext, task_id: str, addBlockedBy: list[str]
    ) -> str:
        try:
            current_agent(context)
            task = update_task(task_id, addBlockedBy, store=store)
            return json.dumps({"status": "updated", "task": asdict(task)}, ensure_ascii=False)
        except (TeamError, TaskError) as exc:
            return failure(exc)

    def complete_team_task(context: ToolContext, task_id: str) -> str:
        try:
            agent = current_agent(context)
            if agent.active_task_id != task_id:
                raise TeamError("只能完成当前执行轮分配的任务")
            completion = complete_task_strict(
                task_id, agent.runtime.agent_id, store=store
            )
            try:
                agent.report_task_finished(registry)
            except Exception as exc:
                return failure(exc)
            return json.dumps(
                {
                    "status": "completed",
                    "task": asdict(completion.task),
                    "unlocked_subjects": completion.unlocked_subjects,
                    "member_state": registry.get(agent.runtime.agent_id).state,
                },
                ensure_ascii=False,
            )
        except (TeamError, TaskError) as exc:
            return failure(exc)

    return {
        "get_team_task": get_team_task,
        "create_team_task": create_team_task,
        "update_team_task": update_team_task,
        "complete_team_task": complete_team_task,
    }
