"""仅向 MasterAgent 暴露的 Agent Team 工具绑定。"""

from dataclasses import asdict
import json

from team.contracts import TeamError
from team.runtime import TeamRuntime
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

    return {"spawn_teammate": spawn_teammate}
