from event import Event, EventType
from cli import cli


class CliEventSink:
    """ 用于在命令行中打印事件的事件接收器。
    
    Args:
        event: 要打印的事件。
    
    """
    def emit(self, event: Event) -> None:

        match event.type:
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
                
            case EventType.COMPACT_STARTED:
                cli.put_agent_other_info(
                    "[auto compact]"
                )

            case EventType.ERROR:
                cli.inform_system_warning(
                    event.data["message"]
                )

