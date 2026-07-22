from types import SimpleNamespace
import pytest
from tools.subagent import extract_text
import tools.subagent as subagent


# ==============================================
# 测试 extract_text 函数
# ==============================================
def test_extract_text_from_string():
    """非 list 类型应该直接转换为字符串。"""

    content = "hello world"

    result = extract_text(content)

    assert result == "hello world"


def test_extract_text_from_integer():
    """非 list 类型应该支持任意对象。"""

    content = 123

    result = extract_text(content)

    assert result == "123"


def test_extract_text_from_none():
    """None 应该转换为空字符串形式。"""

    content = None

    result = extract_text(content)

    assert result == "None"


def test_extract_text_from_text_blocks():
    """多个 text block 应该按换行拼接。"""

    content = [
        SimpleNamespace(
            type="text",
            text="hello",
        ),
        SimpleNamespace(
            type="text",
            text="world",
        ),
    ]

    result = extract_text(content)

    assert result == "hello\nworld"


def test_extract_text_ignores_non_text_blocks():
    """非 text 类型 block 应该被忽略。"""

    content = [
        SimpleNamespace(
            type="text",
            text="hello",
        ),
        SimpleNamespace(
            type="tool_use",
            text="should ignore",
        ),
        SimpleNamespace(
            type="image",
            text="should ignore",
        ),
    ]

    result = extract_text(content)

    assert result == "hello"


def test_extract_text_without_text_blocks():
    """没有 text block 时应该返回空字符串。"""

    content = [
        SimpleNamespace(
            type="tool_use",
            id="tool_001",
        ),
    ]

    result = extract_text(content)

    assert result == ""


def test_extract_text_block_without_text_attribute():
    """text block 缺少 text 属性时应该安全处理。"""

    content = [
        SimpleNamespace(
            type="text",
        ),
    ]

    result = extract_text(content)

    assert result == ""


def test_extract_text_empty_list():
    """空列表应该返回空字符串。"""

    result = extract_text([])

    assert result == ""


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("hello", "hello"),
        (123, "123"),
        (True, "True"),
        (None, "None"),
        # (["not used"], "['not used']"),
    ],
)
def test_extract_text_non_list(content, expected):
    assert extract_text(content) == expected


# ==============================================
# 测试 spawn_subagent 函数
# ==============================================
def test_spawn_subagent_simple_answer(monkeypatch):
    """subagent 无工具调用，直接返回答案。"""

    def fake_call_model(
        messages,
        system_prompt,
        tools,
    ):
        return SimpleNamespace(
            content=[
                SimpleNamespace(
                    type="text",
                    text="这是子代理答案",
                )
            ],
            stop_reason="end_turn",
        )

    monkeypatch.setattr(
        subagent.api,
        "call_model",
        fake_call_model,
    )

    monkeypatch.setattr(
        subagent.cli,
        "put_agent_output",
        lambda x: None,
    )

    result = subagent.spawn_subagent(
        "总结项目"
    )

    assert result == "这是子代理答案"


def test_spawn_subagent_tool_call(monkeypatch):
    """subagent 调用工具后继续回答。"""

    responses = iter(
        [
            # 第一次：请求工具
            SimpleNamespace(
                content=[
                    SimpleNamespace(
                        type="tool_use",
                        id="tool_001",
                        name="test_tool",
                        input={
                            "value": "hello"
                        },
                    )
                ],
                stop_reason="tool_use",
            ),

            # 第二次：最终回答
            SimpleNamespace(
                content=[
                    SimpleNamespace(
                        type="text",
                        text="工具执行完成",
                    )
                ],
                stop_reason="end_turn",
            ),
        ]
    )

    def fake_call_model(
        messages,
        system_prompt,
        tools,
    ):
        return next(responses)

    monkeypatch.setattr(
        subagent.api,
        "call_model",
        fake_call_model,
    )

    # 模拟工具
    monkeypatch.setattr(
        subagent.tool_handler,
        "STANDARD_TOOLS_HANDLERS",
        {
            "test_tool": lambda value: f"result:{value}"
        },
    )

    monkeypatch.setattr(
        subagent.tool_handler,
        "STANDARD_TOOLS_LIST",
        [],
    )

    monkeypatch.setattr(
        subagent.hook,
        "trigger_hooks",
        lambda *args: False,
    )

    monkeypatch.setattr(
        subagent.cli,
        "put_agent_output",
        lambda x: None,
    )

    result = subagent.spawn_subagent(
        "执行任务"
    )

    assert result == "工具执行完成"


def test_spawn_subagent_tool_blocked(monkeypatch):

    responses = iter(
        [
            SimpleNamespace(
                content=[
                    SimpleNamespace(
                        type="tool_use",
                        id="001",
                        name="danger",
                        input={},
                    )
                ],
                stop_reason="tool_use",
            ),

            SimpleNamespace(
                content=[
                    SimpleNamespace(
                        type="text",
                        text="工具被阻止",
                    )
                ],
                stop_reason="end_turn",
            )
        ]
    )

    monkeypatch.setattr(
        subagent.api,
        "call_model",
        lambda **kwargs: next(responses),
    )

    monkeypatch.setattr(
        subagent.hook,
        "trigger_hooks",
        lambda *args: "Permission denied",
    )

    monkeypatch.setattr(
        subagent.cli,
        "put_agent_output",
        lambda x: None,
    )

    result = subagent.spawn_subagent(
        "危险操作"
    )

    assert result == "工具被阻止"
