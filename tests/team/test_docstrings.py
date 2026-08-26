import inspect

from core.agent import MasterSession, create_master_session
from core.runner import run_turn
from team.bus import MessageBus
from team.coordinator import TeamCoordinator
from team.factory import create_teammate_runtime
from team.worker import TeammateWorker
from tools.task_system import TaskStore, bind_task_handlers
from tools.team import bind_team_handlers


def test_agent_team_public_interfaces_have_docstrings():
    """新增公共接口必须延续项目现有的中文 docstring 风格。"""

    interfaces = [
        run_turn,
        MasterSession,
        MasterSession.close,
        create_master_session,
        MessageBus,
        MessageBus.register,
        MessageBus.send,
        MessageBus.receive,
        TeamCoordinator,
        TeamCoordinator.spawn,
        TeamCoordinator.send,
        TeamCoordinator.read_messages,
        TeamCoordinator.list_members,
        TeamCoordinator.snapshot,
        TeamCoordinator.shutdown,
        TeamCoordinator.shutdown_all,
        TeammateWorker,
        TeammateWorker.start,
        TeammateWorker.stop,
        create_teammate_runtime,
        TaskStore.transaction,
        bind_task_handlers,
        bind_team_handlers,
    ]

    assert all(inspect.getdoc(interface) for interface in interfaces)
