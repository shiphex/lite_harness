import pytest
import ast
import textwrap
import tools.todo_write as todo_write

CURRENT_TODOS: list[dict] = []

"""
本测试文件由 chatgpt 生成。
"""


@pytest.fixture(autouse=True)
def restore_current_todos():
    """每个测试完成后恢复 CURRENT_TODOS。"""
    existed = hasattr(todo_write, "CURRENT_TODOS")
    original = getattr(
        todo_write,
        "CURRENT_TODOS",
        None,
    )

    yield

    if existed:
        todo_write.CURRENT_TODOS = original
    elif hasattr(todo_write, "CURRENT_TODOS"):
        delattr(todo_write, "CURRENT_TODOS")


# ============================================================
# _normalize_todos 测试
# ============================================================

def test_normalize_todos_accepts_valid_list():
    """合法列表应原样返回。"""
    todos = [
        {
            "content": "读取文件",
            "status": "pending",
        },
        {
            "content": "修改代码",
            "status": "in_progress",
        },
        {
            "content": "运行测试",
            "status": "completed",
        },
    ]

    result, error = todo_write._normalize_todos(todos)

    assert error is None
    assert result == todos
    assert result is todos


def test_normalize_todos_parses_json_string():
    """JSON 字符串应被解析为任务列表。"""
    todos = """
    [
        {
            "content": "读取文件",
            "status": "pending"
        }
    ]
    """

    result, error = todo_write._normalize_todos(todos)

    assert error is None
    assert result == [
        {
            "content": "读取文件",
            "status": "pending",
        }
    ]



def test_python_literal_can_be_parsed():
    todos = textwrap.dedent("""
    [
        {
            'content': '读取文件',
            'status': 'pending'
        }
    ]
""").strip()

    result = ast.literal_eval(todos)

    assert result == [
        {
            "content": "读取文件",
            "status": "pending",
        }
    ]


def test_normalize_todos_parses_python_literal_string():
    """非标准 JSON 的 Python 字面量应由 ast.literal_eval 解析。"""
    todos = textwrap.dedent("""
    [
        {
            'content': '读取文件',
            'status': 'pending'
        }
    ]
""").strip()

    result, error = todo_write._normalize_todos(todos)

    assert error is None
    assert result == [
        {
            "content": "读取文件",
            "status": "pending",
        }
    ]


def test_normalize_todos_rejects_unparseable_string():
    """无法解析的字符串应返回错误。"""
    result, error = todo_write._normalize_todos(
        "这不是一个有效的列表"
    )

    assert result is None
    assert error == "Error: 无法解析 todos 为列表。"


@pytest.mark.parametrize(
    "todos",
    [
        None,
        123,
        3.14,
        {},
        ("task",),
    ],
)
def test_normalize_todos_rejects_non_list(todos):
    """字符串解析完成后，如果结果不是列表，应返回错误。"""
    result, error = todo_write._normalize_todos(todos)

    assert result is None
    assert error == "Error: todos 必须是列表类型。"


def test_normalize_todos_rejects_json_object_string():
    """能够解析但结果为字典的 JSON 字符串应被拒绝。"""
    result, error = todo_write._normalize_todos(
        '{"content": "读取文件", "status": "pending"}'
    )

    assert result is None
    assert error == "Error: todos 必须是列表类型。"


def test_normalize_todos_rejects_non_dict_item():
    """列表中的元素必须是字典。"""
    todos = [
        {
            "content": "读取文件",
            "status": "pending",
        },
        "修改代码",
    ]

    result, error = todo_write._normalize_todos(todos)

    assert result is None
    assert error == "Error: todos[1] 必须是一个对象类型。"


@pytest.mark.parametrize(
    ("task", "expected_error"),
    [
        (
            {"status": "pending"},
            "Error: todos[0] 必须包含 content 和 status 字段。",
        ),
        (
            {"content": "读取文件"},
            "Error: todos[0] 必须包含 content 和 status 字段。",
        ),
        (
            {},
            "Error: todos[0] 必须包含 content 和 status 字段。",
        ),
    ],
)
def test_normalize_todos_requires_content_and_status(
    task,
    expected_error,
):
    """每个任务必须同时包含 content 和 status。"""
    result, error = todo_write._normalize_todos([task])

    assert result is None
    assert error == expected_error


@pytest.mark.parametrize(
    "status",
    [
        "todo",
        "done",
        "running",
        "",
        None,
        1,
    ],
)
def test_normalize_todos_rejects_invalid_status(status):
    """不支持的任务状态应返回错误。"""
    todos = [
        {
            "content": "读取文件",
            "status": status,
        }
    ]

    result, error = todo_write._normalize_todos(todos)

    assert result is None
    assert error == (
        f"Error: todos[0] 的状态“{status}”无效。"
    )


@pytest.mark.parametrize(
    "status",
    [
        "pending",
        "in_progress",
        "completed",
    ],
)
def test_normalize_todos_accepts_all_valid_statuses(status):
    """三个合法状态都应通过校验。"""
    todos = [
        {
            "content": "测试任务",
            "status": status,
        }
    ]

    result, error = todo_write._normalize_todos(todos)

    assert error is None
    assert result == todos


def test_normalize_todos_accepts_empty_list():
    """空任务列表当前应被允许。"""
    result, error = todo_write._normalize_todos([])

    assert error is None
    assert result == []


# ============================================================
# run_todo_write 测试
# ============================================================

def test_run_todo_write_updates_current_todos(monkeypatch):
    """执行成功后应更新 CURRENT_TODOS。"""
    output_messages = []

    monkeypatch.setattr(
        todo_write.cli,
        "put_agent_output",
        lambda message: output_messages.append(message),
    )

    todos = [
        {
            "content": "读取文件",
            "status": "pending",
        },
        {
            "content": "修改代码",
            "status": "in_progress",
        },
    ]

    result = todo_write.run_todo_write(todos)

    assert result == "更新 2 个任务。"
    assert todo_write.CURRENT_TODOS == todos
    assert len(output_messages) == 1


def test_run_todo_write_outputs_formatted_tasks(monkeypatch):
    """应按照任务状态输出对应图标和任务内容。"""
    output_messages = []

    monkeypatch.setattr(
        todo_write.cli,
        "put_agent_output",
        lambda message: output_messages.append(message),
    )

    todos = [
        {
            "content": "等待执行",
            "status": "pending",
        },
        {
            "content": "正在执行",
            "status": "in_progress",
        },
        {
            "content": "已经完成",
            "status": "completed",
        },
    ]

    result = todo_write.run_todo_write(todos)

    assert result == "更新 3 个任务。"
    assert len(output_messages) == 1

    output = output_messages[0]

    assert "## Current Tasks" in output
    assert "[ ] 等待执行" in output
    assert "[\033[36m▸\033[0m] 正在执行" in output
    assert "[\033[32m✓\033[0m] 已经完成" in output


def test_run_todo_write_accepts_json_string(monkeypatch):
    """run_todo_write 应支持 JSON 字符串输入。"""
    output_messages = []

    monkeypatch.setattr(
        todo_write.cli,
        "put_agent_output",
        lambda message: output_messages.append(message),
    )

    todos = """
    [
        {
            "content": "读取文件",
            "status": "pending"
        }
    ]
    """

    result = todo_write.run_todo_write(todos)

    assert result == "更新 1 个任务。"
    assert todo_write.CURRENT_TODOS == [
        {
            "content": "读取文件",
            "status": "pending",
        }
    ]
    assert len(output_messages) == 1


def test_run_todo_write_returns_error_without_output(
    monkeypatch,
):
    """校验失败时不应调用 CLI 输出。"""
    output_messages = []

    monkeypatch.setattr(
        todo_write.cli,
        "put_agent_output",
        lambda message: output_messages.append(message),
    )

    result = todo_write.run_todo_write(
        [
            {
                "content": "错误任务",
                "status": "invalid",
            }
        ]
    )

    assert result == (
        "Error: todos[0] 的状态“invalid”无效。"
    )
    assert output_messages == []


def test_run_todo_write_does_not_replace_state_on_error(
    monkeypatch,
):
    """输入无效时，不应覆盖之前有效的 CURRENT_TODOS。"""
    monkeypatch.setattr(
        todo_write.cli,
        "put_agent_output",
        lambda message: None,
    )

    original_todos = [
        {
            "content": "原任务",
            "status": "pending",
        }
    ]

    todo_write.CURRENT_TODOS = original_todos

    result = todo_write.run_todo_write(
        [
            {
                "content": "错误任务",
                "status": "unknown",
            }
        ]
    )

    assert result == (
        "Error: todos[0] 的状态“unknown”无效。"
    )
    assert todo_write.CURRENT_TODOS is original_todos


def test_run_todo_write_empty_list(monkeypatch):
    """空列表应输出标题并返回更新 0 个任务。"""
    output_messages = []

    monkeypatch.setattr(
        todo_write.cli,
        "put_agent_output",
        lambda message: output_messages.append(message),
    )

    result = todo_write.run_todo_write([])

    assert result == "更新 0 个任务。"
    assert todo_write.CURRENT_TODOS == []
    assert output_messages == [
        "\033[33m## Current Tasks\033[0m"
    ]