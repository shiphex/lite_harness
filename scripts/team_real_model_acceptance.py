"""Opt-in, multi-scenario Agent Team acceptance against a real model service.

Run with ``python -m scripts.team_real_model_acceptance --help``. Normal pytest
only exercises this entry with an offline adapter.
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
from dataclasses import replace

from builtin.memory import MemoryMode, MemoryPolicy
import core.loop as agent_loop
from core.runtime import RunPolicy, RuntimeFactory, state
from event.sink import NullEventSink
from team.agent import TeamAgent
from team.runtime import TeamRuntime
from tools.task_system import load_task
from tools.team import TEAM_MASTER_TOOLS, bind_team_handlers
from tools.tool_class import ToolContext

from .team_real_model_smoke import SmokeConfig, _execution_category, parse_options


MAX_TURNS = 6
MAX_OUTPUT_TOKENS = 512
_TASK_TOOLS = {"get_team_task", "complete_team_task"}
_MESSAGE_TOOLS = _TASK_TOOLS | {"send_team_message", "receive_team_message"}


def _tool(runtime, name: str, **arguments) -> dict:
    result = runtime.tools.execute(ToolContext(runtime), name, arguments)
    if result.startswith("Team error"):
        raise RuntimeError(f"{name} returned a team error")
    return json.loads(result)


def _restricted_tools(runtime, names: set[str]) -> None:
    runtime.policy.tools_list = [
        tool for tool in runtime.policy.tools_list if tool["name"] in names
    ]
    runtime.tools.allowed_tools = set(names)


class _LiveCase:
    def __init__(self, options: SmokeConfig, case_id: str, tool_names: set[str]):
        self.options = options
        self.case_id = case_id
        self.tool_names = tool_names
        self.events: list[dict] = []
        self.report = {
            "status": "failed",
            "category": "setup_or_runtime_error",
            "model_requests": 0,
            "model_responses": 0,
            "required_tools_executed": False,
            "task_statuses": {},
            "task_owners": {},
            "member_states": {},
            "released": False,
            "teardown_failure_types": [],
        }

    def __enter__(self):
        self.temporary = TemporaryDirectory(prefix=f"team-{self.case_id.lower()}-")
        try:
            return self._setup()
        except Exception:
            self.temporary.cleanup()
            raise

    def _setup(self):
        workspace = Path(self.temporary.name)
        session_id = uuid4().hex[:8]
        model = {
            "api": self.options.api,
            "model_url": self.options.model_url,
            "model_name": self.options.model_name,
            "api_key": self.options.api_key,
        }

        def agent_factory(**kwargs):
            runtime = kwargs["runtime"]
            runtime.policy.max_turns = MAX_TURNS
            runtime.state.max_output_tokens = MAX_OUTPUT_TOKENS
            _restricted_tools(runtime, self.tool_names)
            execute = runtime.tools.execute

            def observed_execute(context, name, args):
                try:
                    result = execute(context, name, args)
                except Exception as exc:
                    self.events.append({
                        "agent_id": runtime.agent_id, "name": name,
                        "arguments": args, "result": None,
                        "error_type": type(exc).__name__,
                    })
                    raise
                self.events.append({
                    "agent_id": runtime.agent_id, "name": name,
                    "arguments": args, "result": result,
                    "error_type": None,
                })
                return result

            runtime.tools.execute = observed_execute
            return TeamAgent(**kwargs)

        self.team = TeamRuntime(
            workspace / ".agents" / "runs" / session_id / "tasks",
            session_id=session_id,
            agent_factory=agent_factory,
        )
        self.master = RuntimeFactory.create(
            agent_name="Master Agent",
            policy=RunPolicy(
                max_turns=0,
                model=model,
                fallback_model=model,
                tools_list=TEAM_MASTER_TOOLS,
                tool_handler=bind_team_handlers(self.team),
            ),
            state=state(max_output_tokens=MAX_OUTPUT_TOKENS, current_model=model),
            memory_policy=MemoryPolicy(mode=MemoryMode.OFF, namespace="master"),
            workspace=workspace,
            session_id=session_id,
            events=NullEventSink(),
        )
        self.original_adapter_factory = agent_loop.create_adapter

        def counted_factory(config):
            adapter = self.original_adapter_factory(config)

            class CountedAdapter:
                def complete(inner_self, request):
                    self.report["model_requests"] += 1
                    response = adapter.complete(replace(
                        request, max_tokens=min(request.max_tokens, MAX_OUTPUT_TOKENS)
                    ))
                    self.report["model_responses"] += 1
                    return response

            return CountedAdapter()

        agent_loop.create_adapter = counted_factory
        return self

    def __exit__(self, _type, _value, _traceback):
        if hasattr(self, "master") and hasattr(self, "team") and not self.report["released"]:
            try:
                self.teardown()
            except Exception as exc:
                self.report["teardown_failure_types"] = sorted(set(
                    [*self.report["teardown_failure_types"], type(exc).__name__]
                ))
        if hasattr(self, "original_adapter_factory"):
            agent_loop.create_adapter = self.original_adapter_factory
        self.temporary.cleanup()

    def spawn(self, name: str) -> str:
        return _tool(self.master, "spawn_teammate", agent_name=name)["agent_id"]

    def create_task(self, subject: str, description: str) -> str:
        return _tool(
            self.master, "create_team_task", subject=subject, description=description
        )["task"]["id"]

    def assigned(self, task_id: str, agent_id: str) -> dict:
        return _tool(self.master, "assign_team_task", task_id=task_id, agent_id=agent_id)

    def worker(self, agent_id: str):
        return self.team.lifecycle_manager.get_agent(agent_id).runtime

    def tool_result(self, agent_id: str, name: str, **arguments) -> dict | None:
        for event in self.events:
            if (event["agent_id"] == agent_id and event["name"] == name
                    and event["arguments"] == arguments and event["error_type"] is None):
                try:
                    result = json.loads(event["result"])
                except (TypeError, ValueError):
                    continue
                if isinstance(result, dict):
                    return result
        return None

    def snapshot(self, task_ids: list[str], agent_ids: list[str]) -> None:
        tasks = {task_id: load_task(task_id, store=self.team.task_store) for task_id in task_ids}
        self.report["task_statuses"] = {task_id: task.status for task_id, task in tasks.items()}
        self.report["task_owners"] = {task_id: task.owner for task_id, task in tasks.items()}
        self.report["member_states"] = {
            agent_id: self.team.member_registry.get(agent_id).state.value
            for agent_id in agent_ids
        }

    def teardown(self) -> dict:
        result = _tool(self.master, "teardown_team")
        self.report["released"] = result["released"] and self.team.member_registry.list() == ()
        self.report["teardown_failure_types"] = sorted({
            failure["type"] for failure in result["failures"].values()
        })
        return result

    def finish(self, valid: bool, run_results: list[dict], required_tools: bool) -> dict:
        self.report["required_tools_executed"] = required_tools
        if any(result.get("status") == "execution_error" for result in run_results):
            error = next(result.get("error") for result in run_results
                         if result.get("status") == "execution_error")
            self.report["category"] = _execution_category(error)
        elif self.report["model_responses"] == 0:
            self.report["category"] = "model_no_response"
        elif not required_tools:
            self.report["category"] = "model_no_required_tool"
        elif not valid:
            self.report["category"] = "state_or_tool_result_mismatch"
        elif not self.report["released"]:
            self.report["category"] = "teardown_failure"
        else:
            self.report["status"] = "passed"
            self.report["category"] = None
        return self.report


def _live_01(case: _LiveCase) -> dict:
    sender = case.spawn("live_sender")
    receiver = case.spawn("live_receiver")
    sender_runtime, receiver_runtime = case.worker(sender), case.worker(receiver)
    token = "LIVE01_" + uuid4().hex[:12]
    send_arguments = json.dumps(
        {"target_id": receiver, "content": token}, ensure_ascii=False, separators=(",", ":")
    )
    send_task = case.create_task(
        "Send team message",
        f"First call send_team_message with exactly these JSON arguments: {send_arguments}. "
        "Do not change either string. After it succeeds call complete_team_task "
        "for your assigned task ID. No files or shell commands are needed.",
    )
    send_result = case.assigned(send_task, sender)
    receive_task = case.create_task(
        "Receive team message",
        f"First call receive_team_message with empty arguments. Check that the "
        f"returned sender_id is exactly {sender} and content is exactly {token}. Only then call "
        "complete_team_task for your assigned task ID. No files or shell commands are needed.",
    )
    receive_result = case.assigned(receive_task, receiver)
    sent = case.tool_result(sender, "send_team_message", target_id=receiver, content=token)
    received = case.tool_result(receiver, "receive_team_message")
    completed = (
        case.tool_result(sender, "complete_team_task", task_id=send_task),
        case.tool_result(receiver, "complete_team_task", task_id=receive_task),
    )
    message_verified = sent == {"status": "sent"} and received == {
        "message": {"sender_id": sender, "target_id": receiver, "content": token}
    }
    required = bool(sent and received and all(
        result and result.get("status") == "completed" for result in completed
    ))
    send_saved = load_task(send_task, store=case.team.task_store)
    receive_saved = load_task(receive_task, store=case.team.task_store)
    states = [case.team.member_registry.get(agent_id).state.value for agent_id in (sender, receiver)]
    valid = (
        message_verified and sender != receiver
        and sender_runtime.session_id == receiver_runtime.session_id == case.master.session_id
        and sender_runtime.state is not receiver_runtime.state
        and send_saved.owner == sender and receive_saved.owner == receiver
        and send_saved.status == receive_saved.status == "completed"
        and states == ["idle", "idle"]
        and send_result["status"] == receive_result["status"] == "completed"
    )
    case.report["message_verified"] = message_verified
    case.snapshot([send_task, receive_task], [sender, receiver])
    case.teardown()
    return case.finish(valid, [send_result, receive_result], required)


def _first_incomplete(case: _LiveCase, original: str, task_id: str) -> tuple[dict, bool]:
    runtime = case.worker(original)
    saved_tools = list(runtime.policy.tools_list)
    runtime.policy.tools_list = [tool for tool in saved_tools if tool["name"] == "get_team_task"]
    runtime.tools.allowed_tools = {"get_team_task"}
    runtime.policy.max_turns = 1
    try:
        first = case.assigned(task_id, original)
    finally:
        runtime.policy.tools_list = saved_tools
        runtime.tools.allowed_tools = {tool["name"] for tool in saved_tools}
        runtime.policy.max_turns = MAX_TURNS
    saved = load_task(task_id, store=case.team.task_store)
    valid = (
        first["status"] == "in_progress" and saved.status == "in_progress"
        and saved.owner == original
        and case.team.member_registry.get(original).state.value == "busy"
    )
    return first, valid


def _live_02(case: _LiveCase) -> dict:
    original = case.spawn("live_owner")
    other = case.spawn("live_other")
    task_id = case.create_task(
        "Resume team task", "Complete this assigned task by calling complete_team_task. "
        "No files or shell commands are needed."
    )
    first, initial_valid = _first_incomplete(case, original, task_id)
    refused_stop = case.master.tools.execute(
        ToolContext(case.master), "shutdown_teammate", {"agent_id": original}
    )
    wrong_owner = case.master.tools.execute(
        ToolContext(case.master), "resume_team_task", {"task_id": task_id, "agent_id": other}
    )
    first_close = case.teardown()
    case.report["initial_teardown_failure_types"] = sorted({
        failure["type"] for failure in first_close["failures"].values()
    })
    rejected = (
        "StopPendingTaskError" in refused_stop and not first_close["released"]
        and first_close["failures"].get(original, {}).get("type") == "StopPendingTaskError"
        and wrong_owner.startswith("Team error")
        and load_task(task_id, store=case.team.task_store).owner == original
    )
    resumed = _tool(case.master, "resume_team_task", task_id=task_id, agent_id=original)
    completed = case.tool_result(original, "complete_team_task", task_id=task_id)
    saved = load_task(task_id, store=case.team.task_store)
    required = bool(completed and completed.get("status") == "completed")
    valid = (
        initial_valid and rejected and required and resumed["status"] == "completed"
        and saved.owner == original and saved.status == "completed"
        and case.team.member_registry.get(original).state.value == "idle"
    )
    case.report["resume_verified"] = valid
    case.snapshot([task_id], [original, other])
    case.teardown()
    return case.finish(valid, [first, resumed], required)


def _live_03(case: _LiveCase) -> dict:
    original = case.spawn("live_failed")
    task_id = case.create_task(
        "Recover failed task", "Complete this assigned task by calling complete_team_task. "
        "No files or shell commands are needed."
    )
    first, initial_valid = _first_incomplete(case, original, task_id)
    fatal = _tool(case.master, "report_team_fatal", agent_id=original,
                  error="controlled acceptance fault")
    first_close = case.teardown()
    case.report["initial_teardown_failure_types"] = sorted({
        failure["type"] for failure in first_close["failures"].values()
    })
    failed_valid = (
        fatal["member_state"] == "failed" and fatal["task_ids"] == [task_id]
        and not first_close["released"]
        and first_close["failures"].get(original, {}).get("type") == "StopPendingTaskError"
        and load_task(task_id, store=case.team.task_store).owner == original
    )
    recovered = _tool(case.master, "recover_failed_team_task", task_id=task_id)
    successor = recovered["agent_id"]
    completed = case.tool_result(successor, "complete_team_task", task_id=task_id)
    saved = load_task(task_id, store=case.team.task_store)
    required = bool(completed and completed.get("status") == "completed")
    valid = (
        initial_valid and failed_valid and required
        and recovered["status"] == "completed"
        and recovered["previous_owner"] == original
        and successor != original and saved.id == task_id
        and saved.owner == successor and saved.status == "completed"
        and saved.reassignments == [{
            "from_owner": original, "to_owner": successor, "reason": "source_failed"
        }]
        and case.team.member_registry.get(original).state.value == "failed"
        and case.team.member_registry.get(successor).state.value == "idle"
    )
    case.report["handoff_verified"] = valid
    case.snapshot([task_id], [original, successor])
    case.teardown()
    return case.finish(valid, [first, recovered], required)


def run_acceptance(options: SmokeConfig) -> dict:
    """Run three independent cases; never count a skipped or incomplete case as passed."""
    report = {
        "status": "failed",
        "api": options.api,
        "model_url": options.model_url,
        "model_name": options.model_name,
        "max_turns_per_run": MAX_TURNS,
        "max_output_tokens_per_request": MAX_OUTPUT_TOKENS,
        "scenarios": {},
    }
    cases = (
        ("LIVE-01", _MESSAGE_TOOLS, _live_01),
        ("LIVE-02", _TASK_TOOLS, _live_02),
        ("LIVE-03", _TASK_TOOLS, _live_03),
    )
    for case_id, names, run in cases:
        case = _LiveCase(options, case_id, names)
        try:
            with case:
                outcome = run(case)
        except Exception as exc:
            outcome = case.report
            outcome["category"] = "setup_or_runtime_error"
            outcome["error_type"] = type(exc).__name__
        report["scenarios"][case_id] = outcome
    if all(item["status"] == "passed" for item in report["scenarios"].values()):
        report["status"] = "passed"
    return report


def main(argv=None) -> int:
    options = parse_options(argv)
    report = run_acceptance(options)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
