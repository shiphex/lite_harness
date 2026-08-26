from event import Event, EventType
from cli import cli


class CliEventSink:
    """ 用于在命令行中打印事件的事件接收器。
    
    Args:
        event: 要打印的事件。
    
    """
    def emit(self, event: Event) -> None:

        match event.type:
            case EventType.SYSTEM_MESSAGE:
                cli.inform_system_info(
                    event.data["trigger"]
                )

            case EventType.ASSISTANT_MESSAGE:
                cli.put_agent_output(
                    event.data["text"]
                )

            case EventType.TOOL_REQUESTED:
                cli.put_agent_other_info(
                    f"[TOOL]: {event.data['tool_name']}"
                )

            case EventType.TOOL_COMPLETED:
                output = str(event.data["output"])
                cli.put_agent_other_info(output[:200])

            case EventType.TOOL_BLOCKED:
                reason = event.data["reason"]
                cli.put_agent_other_info(
                    f"[BLOCKED]: {reason}"
                )

            case EventType.TODO_UPDATED:
                current_todos = event.data["todos"]
                lines = ["\033[33m## Current Tasks\033[0m"]
                for t in current_todos:
                    icon = {"pending": " ", "in_progress": "\033[36m▸\033[0m", "completed": "\033[32m✓\033[0m"}[t["status"]]   # 把整个大字典写在方括号前面，直接根据键取值
                    lines.append(f"    [{icon}] {t['content']}")
                cli.put_agent_output(
                    "\n".join(lines)
                )

            case EventType.TEAM_MEMBER_SPAWNED:
                cli.put_agent_other_info(
                    f"[TEAM] spawned {event.data['member']} "
                    f"({event.data['role']})"
                )

            case EventType.TEAM_MEMBER_STATUS_CHANGED:
                cli.put_agent_other_info(
                    f"[TEAM] {event.data['member']}: {event.data['status']}"
                )

            case EventType.TEAM_MESSAGE_RECEIVED:
                if str(event.data.get("kind")) == "result":
                    cli.put_agent_other_info(
                        f"[TEAM] result from {event.data['sender']}"
                    )

            case EventType.TEAM_MEMBER_STOPPED:
                cli.put_agent_other_info(
                    f"[TEAM] stopped {event.data['member']}"
                )

            case EventType.TEAM_MEMBER_SHUTDOWN_TIMEOUT:
                members = ", ".join(event.data["members"])
                cli.put_agent_other_info(
                    f"[TEAM] shutdown timed out: {members}"
                )
                
            case EventType.COMPACT_STARTED:
                cli.put_agent_other_info(
                    "[auto compact]"
                )

            case EventType.ERROR:
                cli.inform_system_warning(
                    event.data["message"]
                )

