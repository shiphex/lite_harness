"""lite_harness 核心执行入口。

公开入口使用延迟导入，避免 ``team.worker -> core.runner`` 与
``core.agent -> team.coordinator`` 在模块初始化阶段形成循环依赖。
"""


def master_agent(*args, **kwargs):
    """延迟调用 CLI master Agent 入口。"""

    from .agent import master_agent as entrypoint

    return entrypoint(*args, **kwargs)


def create_master_session(*args, **kwargs):
    """延迟创建带 Agent Teams 能力的 master session。"""

    from .agent import create_master_session as factory

    return factory(*args, **kwargs)


def run_turn(*args, **kwargs):
    """延迟执行统一 Agent run 入口。"""

    from .runner import run_turn as execute

    return execute(*args, **kwargs)


def __getattr__(name: str):
    """按需导出需要加载 ``core.agent`` 的类型。"""

    if name == "MasterSession":
        from .agent import MasterSession

        return MasterSession
    raise AttributeError(name)


__all__ = [
    "master_agent",
    "MasterSession",
    "create_master_session",
    "run_turn",
]
