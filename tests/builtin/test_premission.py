import builtin
from builtin.permission import check_deny_list, check_rules, ask_user
from pathlib import Path

def test_check_deny_list():
    # 1. 测试 deny_list 为空的情况
    assert check_deny_list("") is None

    # 2. 测试指令不在拒绝列表中的情况
    assert check_deny_list("test") is None

    # 3. 测试指令在拒绝列表中的情况
    assert check_deny_list("rm -rf /") == "已屏蔽：'rm -rf /' 已在拒绝列表中"


def test_check_rules():
    # 1. 测试 rules 为空的情况
    assert check_rules("read_file", {}) is None
    assert check_rules("write_file", {}) is None
    assert check_rules("powershell", {}) is None

    # 2. 测试 rules 不为空的情况，且指令在 rules 中
    WORKDIR = Path.cwd()
    assert check_rules("read_file", {"path": WORKDIR / "test.txt"})  is None
    assert check_rules("write_file", {"path": WORKDIR / "test.txt"})  is None
    assert check_rules("powershell", {"command": "ls"}) is None

    # 3. 测试 rules 不为空的情况，且指令不在 rules 中
    # assert check_rules("write_file", {"path": "C:\\Users\\ZHmso\\Desktop\\test.txt"})  == "尝试访问的文件路径超出工作目录范围。"
    assert check_rules("powershell", {"command": "rm test.txt"}) == "潜在破坏性指令"


def test_ask_user(monkeypatch):
    # 1. 测试用户同意的情况
    # 模拟用户在终端输入了 "Y" 并回车
    monkeypatch.setattr('builtins.input', lambda _: "Y")
    result = ask_user("test_tool" , {"command": "test_command"}, "确认执行指令吗？")
    assert result == "allow"

    # 2. 测试用户拒绝的情况
    # 模拟用户在终端输入了 "N" 并回车
    monkeypatch.setattr('builtins.input', lambda _: "N")
    result = ask_user("test_tool" , {"command": "test_command"}, "确认执行指令吗？")
    assert result == "deny"


def test_check_permission(monkeypatch):
    # 1. 测试指令不在拒绝列表中的情况
    # 模拟用户在终端输入了 "Y" 并回车
    from types import SimpleNamespace
    block = SimpleNamespace(
        name="powershell",
        input={"command": "rm test.txt"},
    )

    monkeypatch.setattr(
        "builtin.permission.check_deny_list",
        lambda command: None,
    )
    monkeypatch.setattr(
        "builtin.permission.check_rules",
        lambda tool_name, args: None,
    )
    result = builtin.check_permission(block)
    assert result is True

    # 2. 测试指令在拒绝列表中的情况
    monkeypatch.setattr(
        "builtin.permission.check_deny_list",
        lambda command: "已屏蔽：'rm -rf /' 已在拒绝列表中",
    )
    result = builtin.check_permission(block)
    assert result is False

    # 3. 测试指令不在拒绝列表中的情况，但 rules 中有拒绝指令，用户拒绝执行
    monkeypatch.setattr(
        "builtin.permission.check_deny_list",
        lambda command: None,
    )
    monkeypatch.setattr(
        "builtin.permission.check_rules",
        lambda tool_name, args: "潜在破坏性指令",
    )
    monkeypatch.setattr('builtins.input', lambda _: "N")
    result = builtin.check_permission(block)
    assert result is False

    # 4. 测试指令不在拒绝列表中的情况，但 rules 中有拒绝指令，用户同意执行
    monkeypatch.setattr(
        "builtin.permission.check_deny_list",
        lambda command: None,
    )
    monkeypatch.setattr(
        "builtin.permission.check_rules",
        lambda tool_name, args: "潜在破坏性指令",
    )
    monkeypatch.setattr('builtins.input', lambda _: "Y")
    result = builtin.check_permission(block)
    assert result is True
