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
