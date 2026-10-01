"""Explicit, single-task Agent Team smoke against a configured model service.

Run with ``python -m scripts.team_real_model_smoke --help``. This module is not
collected by pytest; the offline tests replace only the external model adapter.
"""

import argparse
from dataclasses import dataclass, field, replace
import json
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from urllib.parse import urlparse
from uuid import uuid4

from builtin.memory import MemoryMode, MemoryPolicy
import core.loop as agent_loop
from core.runtime import RunPolicy, RuntimeFactory, state
from event.sink import NullEventSink
from team.runtime import TeamRuntime
from tools.task_system import load_task
from tools.team import TEAM_MASTER_TOOLS, bind_team_handlers
from tools.tool_class import ToolContext


MAX_TURNS = 3
MAX_OUTPUT_TOKENS = 512
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class SmokeConfig:
    api: str
    model_url: str
    model_name: str
    api_key: str = field(repr=False)

    def __post_init__(self):
        parsed = urlparse(self.model_url)
        if self.api not in {"anthropic", "openai", "gemini", "langchain"}:
            raise ValueError("unsupported API type")
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("model URL must be an absolute HTTP(S) URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("model URL must not contain credentials, a query, or a fragment")
        if not self.model_name.strip() or not self.api_key:
            raise ValueError("model name and credential mode are required")


def parse_options(argv=None) -> SmokeConfig:
    parser = argparse.ArgumentParser(description="Run one explicit Agent Team model smoke")
    parser.add_argument("--api", required=True, choices=("anthropic", "openai", "gemini", "langchain"))
    parser.add_argument("--model-url", required=True)
    parser.add_argument("--model-name", required=True)
    auth = parser.add_mutually_exclusive_group(required=True)
    auth.add_argument("--no-key", action="store_true", help="Use the local no-key placeholder")
    auth.add_argument("--api-key-env", help="Read the credential from this environment variable")
    args = parser.parse_args(argv)
    if args.api_key_env:
        if not _ENV_NAME.fullmatch(args.api_key_env):
            parser.error("invalid credential environment variable name")
        api_key = os.environ.get(args.api_key_env)
        if not api_key:
            parser.error("credential environment variable is empty or unset")
    else:
        api_key = "no-key"
    try:
        return SmokeConfig(args.api, args.model_url, args.model_name, api_key)
    except ValueError as exc:
        parser.error(str(exc))


def _tool(runtime, name: str, **arguments) -> dict:
    result = runtime.tools.execute(ToolContext(runtime), name, arguments)
    if result.startswith("Team error"):
        raise RuntimeError(f"{name} returned a team error")
    return json.loads(result)


def _execution_category(error: str | None) -> str:
    error_type = (error or "").split(":", 1)[0]
    if error_type == "RuntimeError" and "Exceeded max retry attempts" in (error or ""):
        return "service_or_protocol_error"
    if error_type in {"AuthenticationError", "PermissionDeniedError"}:
        return "credentials_unavailable"
    if error_type in {
        "APIConnectionError", "APITimeoutError", "APIStatusError", "BadRequestError",
        "RateLimitError", "InternalServerError", "NotFoundError",
        "UnprocessableEntityError", "ConnectionError", "TimeoutError",
    }:
        return "service_or_protocol_error"
    return "execution_error"


def run_smoke(options: SmokeConfig) -> dict:
    """Exercise real team composition and query_loop in a disposable workspace."""
    model = {
        "api": options.api,
        "model_url": options.model_url,
        "model_name": options.model_name,
        "api_key": options.api_key,
    }
    report = {
        "status": "failed",
        "category": "setup_error",
        "api": options.api,
        "model_url": options.model_url,
        "model_name": options.model_name,
        "max_turns": MAX_TURNS,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "model_requests": 0,
        "model_responses": 0,
        "turns": 0,
        "completion_tool_called": False,
        "task_status": None,
        "owner_matches": False,
        "member_state": None,
        "released": False,
        "teardown_failure_types": [],
    }
    with TemporaryDirectory(prefix="team-real-model-smoke-") as temporary:
        workspace = Path(temporary)
        session_id = uuid4().hex[:8]
        team = TeamRuntime(workspace / ".agents" / "runs" / session_id / "tasks", session_id=session_id)
        handlers = bind_team_handlers(team)
        master = RuntimeFactory.create(
            agent_name="Master Agent",
            policy=RunPolicy(
                max_turns=0,
                model=model,
                fallback_model=model,
                tools_list=TEAM_MASTER_TOOLS,
                tool_handler=handlers,
            ),
            state=state(max_output_tokens=MAX_OUTPUT_TOKENS, current_model=model),
            memory_policy=MemoryPolicy(mode=MemoryMode.OFF, namespace="master"),
            workspace=workspace,
            session_id=session_id,
            events=NullEventSink(),
        )
        member = _tool(master, "spawn_teammate", agent_name="smoke_worker")
        agent_id = member["agent_id"]
        task = _tool(
            master, "create_team_task",
            subject="Complete the smoke task",
            description="Call complete_team_task for this task ID. No files or commands are needed.",
        )["task"]
        task_id = task["id"]
        worker = team.lifecycle_manager.get_agent(agent_id)
        worker.runtime.policy.max_turns = MAX_TURNS
        worker.runtime.state.max_output_tokens = MAX_OUTPUT_TOKENS
        smoke_tools = {"get_team_task", "complete_team_task"}
        worker.runtime.policy.tools_list = [
            tool for tool in worker.runtime.policy.tools_list if tool["name"] in smoke_tools
        ]
        worker.runtime.tools.allowed_tools = smoke_tools

        original_factory = agent_loop.create_adapter

        def counted_factory(config):
            adapter = original_factory(config)

            class CountingAdapter:
                def complete(self, request):
                    report["model_requests"] += 1
                    response = adapter.complete(replace(request, max_tokens=min(request.max_tokens, MAX_OUTPUT_TOKENS)))
                    report["model_responses"] += 1
                    if any(
                        call.name == "complete_team_task" and call.input.get("task_id") == task_id
                        for call in response.tool_calls
                    ):
                        report["completion_tool_called"] = True
                    return response

            return CountingAdapter()

        agent_loop.create_adapter = counted_factory
        try:
            assigned = _tool(master, "assign_team_task", task_id=task_id, agent_id=agent_id)
        finally:
            agent_loop.create_adapter = original_factory

        report["turns"] = worker.runtime.state.turn_count
        saved = load_task(task_id, store=team.task_store)
        report["task_status"] = saved.status
        report["owner_matches"] = saved.owner == agent_id
        report["member_state"] = team.member_registry.get(agent_id).state.value
        report["run_reason"] = assigned.get("run_reason")
        report["error_type"] = (assigned.get("error") or "").split(":", 1)[0] or None

        teardown = _tool(master, "teardown_team")
        report["released"] = teardown["released"] and team.member_registry.list() == ()
        report["teardown_failure_types"] = sorted({
            failure["type"] for failure in teardown["failures"].values()
        })
        if assigned["status"] == "execution_error":
            report["category"] = _execution_category(assigned.get("error"))
        elif report["model_responses"] == 0:
            report["category"] = "model_no_response"
        elif not report["completion_tool_called"]:
            report["category"] = "model_no_completion_tool"
        elif saved.status != "completed" or saved.owner != agent_id or report["member_state"] != "idle":
            report["category"] = "task_or_member_incomplete"
        elif not report["released"]:
            report["category"] = "teardown_failure"
        else:
            report["status"] = "passed"
            report["category"] = None
    return report


def main(argv=None) -> int:
    options = parse_options(argv)
    try:
        report = run_smoke(options)
    except Exception as exc:
        report = {"status": "failed", "category": "setup_or_runtime_error", "error_type": type(exc).__name__}
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
