import json
import re
from threading import Barrier
from time import monotonic, sleep

from core import agent
from event import MemoryEventSink
import team.worker as worker_module
from tools.tool_class import ToolContext


def test_master_session_runs_two_team_tasks_through_tool_executor(
    monkeypatch,
    tmp_path,
):
    """使用 fake run 验证 lead tools、Worker、共享任务和关闭的完整链路。"""

    class FakeConfig:
        def get_model_config(self):
            return {
                "api": "fake",
                "model_name": "fake-model",
                "fallback_model_name": "fake-model",
            }

        def get_content_length(self):
            return {"MAIN_OUTPUT_TOKENS": 128}

        def get_path_config(self, name):
            assert name == "project_path"
            return tmp_path

        def get_team_config(self):
            return {"MAX_MEMBERS": 3}

    barrier = Barrier(2)

    def fake_run_turn(runtime, prompt):
        runtime.state.messages.append({"role": "user", "content": prompt})
        barrier.wait(timeout=2)
        task_id = re.search(r"task_[0-9a-f]{8}", prompt).group(0)
        runtime.policy.tool_handler["claim_task"](
            ToolContext(runtime),
            task_id=task_id,
        )
        completion = runtime.policy.tool_handler["complete_task"](
            ToolContext(runtime),
            task_id=task_id,
        )
        runtime.state.messages.append({
            "role": "assistant",
            "content": [{"type": "text", "text": completion}],
        })
        return runtime.state, {"reason": "completed"}

    monkeypatch.setattr(agent.config, "Config", FakeConfig)
    monkeypatch.setattr(worker_module, "run_turn", fake_run_turn)
    session = agent.create_master_session(
        [],
        {},
        events=MemoryEventSink(),
        interaction=object(),
    )
    runtime = session.runtime
    context = ToolContext(runtime)

    first_created = runtime.tools.execute(
        context,
        "create_task",
        {"subject": "review runtime", "description": ""},
    )
    second_created = runtime.tools.execute(
        context,
        "create_task",
        {"subject": "review events", "description": ""},
    )
    first_id = re.search(r"task_[0-9a-f]{8}", first_created).group(0)
    second_id = re.search(r"task_[0-9a-f]{8}", second_created).group(0)

    runtime.tools.execute(
        context,
        "spawn_teammate",
        {
            "name": "alice",
            "role": "runtime reviewer",
            "prompt": f"claim and review {first_id}",
        },
    )
    runtime.tools.execute(
        context,
        "spawn_teammate",
        {
            "name": "bob",
            "role": "event reviewer",
            "prompt": f"claim and review {second_id}",
        },
    )

    deadline = monotonic() + 2
    while monotonic() < deadline:
        if (
            session.team.tasks.load(first_id).status == "completed"
            and session.team.tasks.load(second_id).status == "completed"
        ):
            break
        sleep(0.01)

    messages = []
    deadline = monotonic() + 2
    while len(messages) < 2 and monotonic() < deadline:
        messages.extend(json.loads(
            runtime.tools.execute(context, "read_messages", {})
        ))
        if len(messages) < 2:
            sleep(0.01)
    assert {message["sender"] for message in messages} == {"alice", "bob"}
    assert session.team.tasks.load(first_id).status == "completed"
    assert session.team.tasks.load(second_id).status == "completed"

    runtime.tools.execute(context, "shutdown_teammate", {"name": "alice"})
    runtime.tools.execute(context, "shutdown_teammate", {"name": "bob"})
    session.close()
