from hook.permission_hook import permission_hook


def test_permission_hook(monkeypatch):
    
    # 1. 测试指令在拒绝列表中的情况
    from types import SimpleNamespace
    block = SimpleNamespace(
        name = "powershell",
        input = {"command": "rm -rf /"},
    )

    result = permission_hook(block)
    assert result == "权限已被拒绝列表拒绝"


    # 2. 测试指令不在拒绝列表中，但 rules 中有拒绝指令，用户拒绝执行
    block = SimpleNamespace(
        name = "powershell",
        input = {"command": "rm test.txt"},
    )
    monkeypatch.setattr('builtins.input', lambda _: "N")
    result = permission_hook(block)
    assert result == "权限已被用户拒绝"



    # 3. 测试指令不在拒绝列表中，但 rules 中有拒绝指令，用户选择执行
    block = SimpleNamespace(
        name = "powershell",
        input = {"command": "rm test.txt"},
    )
    monkeypatch.setattr('builtins.input', lambda _: "Y")
    result = permission_hook(block)
    assert result is None
