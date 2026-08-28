import re
from threading import Barrier

from core import agent
from core.control import RunDirective
from core.session_driver import SessionDriver
from event import MemoryEventSink
import core.session_driver as driver_module
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

    outcome = runtime.tools.execute(
        context,
        "wait_teammates",
        {"members": ["alice", "bob"], "timeout_seconds": 2},
    )
    assert outcome.directive == RunDirective.SUSPEND
    assert outcome.suspend.payload == {
        "members": ["alice", "bob"],
        "timeout_seconds": 2,
    }

    wait_result = session.team.wait_for_results(
        runtime,
        outcome.suspend.payload["members"],
        timeout_seconds=outcome.suspend.payload["timeout_seconds"],
    )
    assert {message.sender for message in wait_result.messages} == {"alice", "bob"}
    assert wait_result.pending == ()
    assert session.team.tasks.load(first_id).status == "completed"
    assert session.team.tasks.load(second_id).status == "completed"

    runtime.tools.execute(context, "shutdown_teammate", {"name": "alice"})
    runtime.tools.execute(context, "shutdown_teammate", {"name": "bob"})
    session.close()


def test_session_driver_resumes_lead_after_real_mailbox_result(
    monkeypatch,
    tmp_path,
):
    """使用真实 Worker/Queue 验证 lead 挂起后只恢复一次。"""

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

    def fake_worker_run(runtime, prompt):
        runtime.state.messages.append({"role": "user", "content": prompt})
        runtime.state.messages.append({
            "role": "assistant",
            "content": [{"type": "text", "text": "worker result"}],
        })
        return runtime.state, {"reason": "completed"}

    monkeypatch.setattr(agent.config, "Config", FakeConfig)
    monkeypatch.setattr(worker_module, "run_turn", fake_worker_run)
    session = agent.create_master_session(
        [],
        {},
        events=MemoryEventSink(),
        interaction=object(),
    )
    runtime = session.runtime
    inputs = []

    def fake_lead_run(current_runtime, user_input):
        inputs.append(user_input)
        if len(inputs) == 1:
            current_runtime.tools.execute(
                ToolContext(current_runtime),
                "spawn_teammate",
                {
                    "name": "alice",
                    "role": "reviewer",
                    "prompt": "review runtime",
                },
            )
            outcome = current_runtime.tools.execute(
                ToolContext(current_runtime),
                "wait_teammates",
                {"members": ["alice"], "timeout_seconds": 2},
            )
            return current_runtime.state, {
                "reason": "suspended",
                "request": outcome.suspend,
            }
        return current_runtime.state, {"reason": "completed"}

    monkeypatch.setattr(driver_module, "run_turn", fake_lead_run)

    _, status = SessionDriver(runtime=runtime, team=session.team).submit("start")

    assert status == {"reason": "completed"}
    assert len(inputs) == 2
    assert inputs[1].count("worker result") == 1
    assert '"completed": [\n    "alice"\n  ]' in inputs[1]
    session.close()
