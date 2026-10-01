# 测试

项目使用 `uv` 管理测试依赖。默认执行整个测试目录：

```powershell
uv run --no-sync pytest -q tests
```

也可以按文件或目录执行：

```powershell
uv run --no-sync pytest -q tests/tools/test_todo_write.py tests/tools/test_tool_handler.py
```

也支持 pytest 的 marker 或关键字筛选：

```powershell
uv run --no-sync pytest -q -m <marker> tests
uv run --no-sync pytest -q -k todo tests
```

测试改名或删除后，IDE/CI 应刷新测试发现，并使用测试文件、目录或 marker 选择测试，避免继续执行缓存的旧 node ID。

## Agent Team 的测试层次

`tests/team/` 的状态、契约、失败和集成测试默认使用 fake loop / fake adapter，不依赖模型服务；`tests/team/test_real_model_smoke.py` 与 `tests/team/test_real_model_acceptance.py` 也是离线入口验证。真实模型测试须**显式**运行 `scripts/team_real_model_smoke.py` 或 `scripts/team_real_model_acceptance.py`，不会因普通 pytest 自动触发。

单成员 smoke 验证基本任务闭环；扩展验收分别验证双成员消息、未完成任务续跑和 FAILED 任务交接。交互式 Master 的模型工具选择单独观察，不计入扩展验收的脚本化通过条件。环境检查、PowerShell 命令、JSON 判定和排查方法见[Agent Team 运行测试笔记](../note/s13_agent_team_testing_note.md)；正式检查项见[测试计划](<../features/agent team/07_test_plan.md>)。
