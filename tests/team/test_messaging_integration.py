import json
from types import SimpleNamespace

from team.contracts import MemberState
from team.runtime import TeamRuntime
from core.runtime import RuntimeFactory
from tools.team import TEAM_MASTER_TOOLS
from tools.tool_class import ToolContext
from tools.tool_handler import STANDARD_TOOLS_LIST


class FakeRuntimeFactory:
    @staticmethod
    def create(**kwargs):
        return SimpleNamespace(
            agent_id=f"{kwargs['agent_name']}-runtime-id",
            agent_name=kwargs["agent_name"],
            session_id=kwargs["session_id"],
            policy=kwargs["policy"],
            state=kwargs["state"],
            paths=SimpleNamespace(workspace=kwargs["workspace"]),
        )


def _team(tmp_path, *, runtime_factory=FakeRuntimeFactory):
    team = TeamRuntime(
        tmp_path / "tasks",
        session_id="session-1",
        runtime_factory=runtime_factory,
    )
    parent = SimpleNamespace(
        session_id="session-1",
        policy=SimpleNamespace(
            model={"api": "fake", "model_name": "primary"},
            fallback_model={"api": "fake", "model_name": "fallback"},
        ),
        state=SimpleNamespace(max_output_tokens=1024),
        paths=SimpleNamespace(workspace=tmp_path),
    )
    return team, parent


def test_spawned_members_exchange_messages_without_starting_execution(tmp_path):
    team, parent = _team(tmp_path)
    first = team.lifecycle_manager.spawn(parent_runtime=parent, agent_name="first")
    second = team.lifecycle_manager.spawn(parent_runtime=parent, agent_name="second")
    first_agent = team.lifecycle_manager.get_agent(first.agent_id)
    second_agent = team.lifecycle_manager.get_agent(second.agent_id)

    first_agent.mailbox_handle.send(second.agent_id, "hello")
    received = second_agent.mailbox_handle.receive()

    assert (received.sender_id, received.target_id, received.content) == (
        first.agent_id, second.agent_id, "hello"
    )
    assert first_agent.runtime.state.messages == []
    assert second_agent.runtime.state.messages == []
    assert team.member_registry.get(first.agent_id).state is MemberState.IDLE
    assert team.member_registry.get(second.agent_id).state is MemberState.IDLE


def test_message_operations_never_run_agent_or_transition_member(tmp_path, monkeypatch):
    team, parent = _team(tmp_path)
    first = team.lifecycle_manager.spawn(parent_runtime=parent, agent_name="first")
    second = team.lifecycle_manager.spawn(parent_runtime=parent, agent_name="second")
    first_agent = team.lifecycle_manager.get_agent(first.agent_id)
    second_agent = team.lifecycle_manager.get_agent(second.agent_id)

    def unexpected(*args, **kwargs):
        raise AssertionError("message operations must not start execution or transition members")

    monkeypatch.setattr(type(first_agent), "run", unexpected)
    monkeypatch.setattr(team.member_registry, "transition", unexpected)

    first_agent.mailbox_handle.send(second.agent_id, "handle")
    assert second_agent.mailbox_handle.receive().content == "handle"
    send = first_agent.runtime.policy.tool_handler["send_team_message"]
    receive = second_agent.runtime.policy.tool_handler["receive_team_message"]
    assert json.loads(
        send(ToolContext(first_agent.runtime), target_id=second.agent_id, content="tool")
    ) == {"status": "sent"}
    assert json.loads(receive(ToolContext(second_agent.runtime)))["message"]["content"] == "tool"


def test_message_tools_are_teamagent_only_and_return_json(tmp_path):
    team, parent = _team(tmp_path)
    first = team.lifecycle_manager.spawn(parent_runtime=parent, agent_name="first")
    second = team.lifecycle_manager.spawn(parent_runtime=parent, agent_name="second")
    first_runtime = team.lifecycle_manager.get_agent(first.agent_id).runtime
    second_runtime = team.lifecycle_manager.get_agent(second.agent_id).runtime
    names = {tool["name"] for tool in first_runtime.policy.tools_list}

    assert {"send_team_message", "receive_team_message"} <= names
    assert names == set(first_runtime.policy.tool_handler)
    assert {"read_file", "glob", "load_skill"} <= names
    assert {"send_team_message", "receive_team_message"}.isdisjoint(
        {tool["name"] for tool in STANDARD_TOOLS_LIST + TEAM_MASTER_TOOLS}
    )

    send = first_runtime.policy.tool_handler["send_team_message"]
    receive = second_runtime.policy.tool_handler["receive_team_message"]
    assert json.loads(
        send(ToolContext(first_runtime), target_id=second.agent_id, content="hello")
    ) == {"status": "sent"}
    assert json.loads(receive(ToolContext(second_runtime))) == {
        "message": {
            "sender_id": first.agent_id,
            "target_id": second.agent_id,
            "content": "hello",
        }
    }
    assert json.loads(receive(ToolContext(second_runtime))) == {"message": None}


def test_message_tool_rejects_context_with_forged_runtime_identity(tmp_path):
    team, parent = _team(tmp_path)
    member = team.lifecycle_manager.spawn(parent_runtime=parent, agent_name="first")
    owned_runtime = team.lifecycle_manager.get_agent(member.agent_id).runtime
    forged_runtime = SimpleNamespace(agent_id=member.agent_id)
    send = owned_runtime.policy.tool_handler["send_team_message"]

    assert send(
        ToolContext(forged_runtime), target_id=member.agent_id, content="spoof"
    ).startswith("Team error [MessageUnavailableError]:")
    assert team.lifecycle_manager.get_agent(member.agent_id).mailbox_handle.receive() is None


def test_message_tool_reports_typed_target_failure(tmp_path):
    team, parent = _team(tmp_path)
    member = team.lifecycle_manager.spawn(parent_runtime=parent, agent_name="first")
    runtime = team.lifecycle_manager.get_agent(member.agent_id).runtime
    send = runtime.policy.tool_handler["send_team_message"]

    assert send(ToolContext(runtime), target_id="unknown", content="hello").startswith(
        "Team error [MessageTargetNotFoundError]:"
    )


def test_real_runtime_tool_executor_routes_messages_without_model(tmp_path):
    team, parent = _team(tmp_path, runtime_factory=RuntimeFactory)
    first = team.lifecycle_manager.spawn(parent_runtime=parent, agent_name="first")
    second = team.lifecycle_manager.spawn(parent_runtime=parent, agent_name="second")
    first_runtime = team.lifecycle_manager.get_agent(first.agent_id).runtime
    second_runtime = team.lifecycle_manager.get_agent(second.agent_id).runtime

    sent = first_runtime.tools.execute(
        ToolContext(first_runtime),
        "send_team_message",
        {"target_id": second.agent_id, "content": "from actual executor"},
    )
    received = second_runtime.tools.execute(
        ToolContext(second_runtime), "receive_team_message", {}
    )

    assert json.loads(sent) == {"status": "sent"}
    assert json.loads(received)["message"] == {
        "sender_id": first.agent_id,
        "target_id": second.agent_id,
        "content": "from actual executor",
    }
