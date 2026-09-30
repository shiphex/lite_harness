import ast
from pathlib import Path

import pytest

from team.task_tools import TEAM_AGENT_TASK_TOOLS


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _tree(relative_path):
    return ast.parse((PROJECT_ROOT / relative_path).read_text(encoding="utf-8"))


def _dotted_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else None
    return None


class _ScopedAliasGuard(ast.NodeVisitor):
    """Follow simple aliases without sharing local names across functions."""

    def __init__(self, names):
        self.names = set(names)
        self.matches = []

    def _visit_scope(self, body):
        outer = self.names
        self.names = outer.copy()
        for node in body:
            self.visit(node)
        self.names = outer

    def visit_FunctionDef(self, node):
        self._visit_scope(node.body)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        outer = self.names
        self.names = outer.copy()
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                class_names = self.names
                self.names = outer.copy()
                self.visit(child)
                self.names = class_names
            else:
                self.visit(child)
        self.names = outer

    def _is_alias_source(self, source):
        raise NotImplementedError

    def visit_Assign(self, node):
        self.visit(node.value)
        source = _dotted_name(node.value)
        for target in node.targets:
            target_name = _dotted_name(target)
            if target_name:
                if self._is_alias_source(source):
                    self.names.add(target_name)
                else:
                    self.names.discard(target_name)

    def visit_AnnAssign(self, node):
        if node.value is not None:
            self.visit(node.value)
            target_name = _dotted_name(node.target)
            if target_name:
                if self._is_alias_source(_dotted_name(node.value)):
                    self.names.add(target_name)
                else:
                    self.names.discard(target_name)

    def visit_Call(self, node):
        if self._is_target_call(node):
            self.matches.append(node)
        self.generic_visit(node)

    def _is_target_call(self, node):
        raise NotImplementedError


class _FactoryCreateGuard(_ScopedAliasGuard):
    def __init__(self):
        super().__init__({
            "RuntimeFactory", "runtime_factory", "self.runtime_factory",
            "core.runtime.RuntimeFactory",
        })

    def visit_ImportFrom(self, node):
        if node.module == "core.runtime":
            self.names.update(
                alias.asname or alias.name
                for alias in node.names if alias.name == "RuntimeFactory"
            )
        elif node.module == "core":
            self.names.update(
                f"{alias.asname or alias.name}.RuntimeFactory"
                for alias in node.names if alias.name == "runtime"
            )

    def visit_Import(self, node):
        self.names.update(
            f"{alias.asname}.RuntimeFactory"
            for alias in node.names
            if alias.name == "core.runtime" and alias.asname
        )

    def _is_alias_source(self, source):
        return source in self.names

    def _is_target_call(self, node):
        return (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "create"
            and _dotted_name(node.func.value) in self.names
        )


def _factory_create_calls(tree):
    guard = _FactoryCreateGuard()
    guard.visit(tree)
    return guard.matches


def _direct_bus_accesses(tree):
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr in {"_bus", "_mailboxes", "_mailbox", "message_bus", "_message_bus"}
    ]


def _message_bus_imports(tree):
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        and any(alias.name == "team.messaging" for alias in node.names)
        or isinstance(node, ast.ImportFrom)
        and node.module in {"messaging", "team.messaging"}
        and any(alias.name == "MessageBus" for alias in node.names)
    ]


def _non_goal_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(alias.name for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
    forbidden = (
        "worktree", "scheduler", "evict", "idle_timeout", "idletimeout",
        "auto_claim", "autoclaim",
    )
    return {name for name in names if any(part in name.lower() for part in forbidden)}


class _AgentClaimGuard(_ScopedAliasGuard):
    def __init__(self):
        super().__init__({"claim_task", "claim_task_strict"})

    def visit_ImportFrom(self, node):
        for alias in node.names:
            if alias.name in {"claim_task", "claim_task_strict"}:
                self.names.add(alias.asname or alias.name)
                self.matches.append(node)

    def _is_alias_source(self, source):
        return bool(source) and (
            source in self.names
            or source.rsplit(".", 1)[-1] in {"claim_task", "claim_task_strict"}
        )

    def _is_target_call(self, node):
        name = _dotted_name(node.func)
        return bool(name) and (
            name in self.names
            or name.rsplit(".", 1)[-1] in {"claim_task", "claim_task_strict"}
        )


def _agent_claim_references(tree):
    guard = _AgentClaimGuard()
    guard.visit(tree)
    return guard.matches


def test_registry_does_not_import_runtime_factory():
    tree = _tree("team/registry.py")
    assert not any(
        isinstance(node, ast.Import)
        and any(alias.name.startswith("core.runtime") for alias in node.names)
        or isinstance(node, ast.ImportFrom)
        and (
            node.module == "core.runtime"
            or node.module == "core"
            and any(alias.name == "runtime" for alias in node.names)
        )
        for node in ast.walk(tree)
    )
    assert not _factory_create_calls(tree)

def test_team_package_does_not_add_task_scheduler_or_worktree_modules():
    assert not (PROJECT_ROOT / "team" / "scheduler.py").exists()
    assert not (PROJECT_ROOT / "team" / "worktree.py").exists()
    for path in (*sorted((PROJECT_ROOT / "team").glob("*.py")), PROJECT_ROOT / "tools" / "team.py"):
        assert not _non_goal_names(_tree(path.relative_to(PROJECT_ROOT))), path
    assert not any("claim" in tool["name"] for tool in TEAM_AGENT_TASK_TOOLS)
    for relative in ("team/agent.py", "team/task_tools.py", "team/messaging_tools.py"):
        assert not _agent_claim_references(_tree(relative)), relative


def test_teamagent_creation_entrypoint_is_lifecycle_manager():
    lifecycle = PROJECT_ROOT / "team" / "lifecycle.py"
    assert len(_factory_create_calls(_tree(lifecycle.relative_to(PROJECT_ROOT)))) == 1
    for path in (*sorted((PROJECT_ROOT / "team").glob("*.py")), PROJECT_ROOT / "tools" / "team.py"):
        if path != lifecycle:
            assert not _factory_create_calls(_tree(path.relative_to(PROJECT_ROOT))), path


def test_teamagent_uses_existing_query_loop_without_new_runtime_type():
    tree = _tree("team/agent.py")
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "core.loop"
        and any(alias.name == "query_loop" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert any(
        isinstance(node, ast.Call) and _dotted_name(node.func) == "self._run_loop"
        for node in ast.walk(tree)
    )
    for path in (PROJECT_ROOT / "team").glob("*.py"):
        assert not any(
            isinstance(node, ast.ClassDef) and node.name == "TeamAgentRuntime"
            or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "query_loop"
            for node in ast.walk(_tree(path.relative_to(PROJECT_ROOT)))
        ), path


def test_teamagent_tools_do_not_access_message_bus_directly():
    for relative in ("team/agent.py", "team/messaging_tools.py", "team/task_tools.py"):
        tree = _tree(relative)
        assert not _direct_bus_accesses(tree), relative
        assert not _message_bus_imports(tree), relative


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("from core.runtime import RuntimeFactory as Factory\nFactory.create()", True),
        ("import core.runtime as runtime\nruntime.RuntimeFactory.create()", True),
        ("self.runtime_factory.create()", True),
        ("factory = self.runtime_factory\nfactory.create()", True),
        ("factory = RuntimeFactory\nfactory.create()", True),
        ("self.factory = RuntimeFactory\nself.factory.create()", True),
        (
            "def build():\n    factory = RuntimeFactory\n"
            "def unrelated():\n    factory = task_store\n    factory.create()",
            False,
        ),
        ("task_store.create()", False),
    ],
)
def test_ast_factory_guard_detects_real_construction_calls(source, expected):
    assert bool(_factory_create_calls(ast.parse(source))) is expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("agent.message_bus._mailboxes[agent_id]", True),
        ("agent.message_bus.send(sender_id='a', target_id='b', content='x')", True),
        ("self.mailbox_handle._bus.send(sender_id='a', target_id='b', content='x')", True),
        ("agent.mailbox_handle.receive()", False),
    ],
)
def test_ast_mailbox_guard_detects_direct_bus_access(source, expected):
    assert bool(_direct_bus_accesses(ast.parse(source))) is expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("from .messaging import MessageBus", True),
        ("from team.messaging import MessageBus as Bus", True),
        ("import team.messaging as messaging", True),
        ("from .messaging import MailboxHandle", False),
    ],
)
def test_ast_message_bus_import_guard_detects_direct_dependency(source, expected):
    assert bool(_message_bus_imports(ast.parse(source))) is expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("def evict_idle_members(): pass", {"evict_idle_members"}),
        ("class TeamScheduler: pass", {"TeamScheduler"}),
        ("from tools.cron_scheduler import start", {"tools.cron_scheduler"}),
        ("def send_message(): pass", set()),
    ],
)
def test_ast_non_goal_guard_detects_unsupported_capabilities(source, expected):
    assert _non_goal_names(ast.parse(source)) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("from tools.task_system import claim_task_strict as take\ntake('t', 'a')", True),
        ("store.claim_task_strict('t', 'a')", True),
        ("store.claim_task('t', 'a')", True),
        (
            "import tools.task_system as task_api\n"
            "take = task_api.claim_task_strict\ntake('t', 'a')",
            True,
        ),
        ("complete_task_strict('t', 'a')", False),
    ],
)
def test_ast_agent_claim_guard_detects_direct_claims(source, expected):
    assert bool(_agent_claim_references(ast.parse(source))) is expected
