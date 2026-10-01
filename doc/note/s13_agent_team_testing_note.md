# Agent Team 本地模型运行测试笔记

这份笔记用于以后在 Windows PowerShell 中复测 TeamAgent。正式检查项与接受状态见[测试计划](<../features/agent team/07_test_plan.md>)；组件关系见[架构说明](../architecture/agent_team.md)。下面的模型 ID 和地址对应 2026-10-01 使用的本地 llama.cpp 服务；服务或模型变化时，以 `/v1/models` 的实际返回值为准。

## 1. 准备模型服务与 Python 环境

在项目根目录执行 `uv sync`，确保 `.venv/Scripts/python.exe` 可用。使用已有的本地服务时，先检查：

```powershell
(Invoke-RestMethod http://127.0.0.1:8000/health).status
(Invoke-RestMethod http://127.0.0.1:8000/v1/models).data.id
```

期望分别得到 `ok` 和 `unsloth/Qwen3.5-4B-GGUF:UD-Q6_K_XL`。端口可达只证明服务已启动，不能代替工具调用和任务状态的验收。

如需重新启动相同的 llama.cpp 容器，可把 `$modelCache` 改成自己的模型缓存目录：

```powershell
$modelCache = 'D:\Models\GGUF\Qwen3.5-4B-GGUF'
docker run --rm --gpus all `
  --name qwen35-llama-cpp `
  -p 8000:8000 `
  -v "${modelCache}:/root/.cache/huggingface" `
  ghcr.io/ggml-org/llama.cpp:server-cuda `
  -hf unsloth/Qwen3.5-4B-GGUF:UD-Q6_K_XL `
  --host 0.0.0.0 --port 8000 `
  -c 40960 -ngl 99 --reasoning off --jinja
```

模型下载若确需 Hugging Face 凭据，请先以安全方式设置宿主机环境变量，再给 `docker run` 增加 `-e HF_TOKEN`；不要把令牌值写进命令、文档或测试报告。下面的项目 API 参数 `--no-key` / `--api_key no-key` 仅是本地无鉴权占位值。

## 2. 按顺序运行测试

从项目根目录运行；`--model-url` 是两个手动脚本的参数，交互式 `main.py` 使用 `--model_url`。

```powershell
$python = '.\.venv\Scripts\python.exe'

# 1. 离线回归；默认不会请求模型
& $python -B -m pytest -q -p no:cacheprovider

# 2. 单成员真实模型 smoke
& $python -B -m scripts.team_real_model_smoke `
  --api openai --model-url http://127.0.0.1:8000/v1 `
  --model-name unsloth/Qwen3.5-4B-GGUF:UD-Q6_K_XL --no-key

# 3. 双成员与恢复场景；只在显式执行时请求模型
& $python -B -m scripts.team_real_model_acceptance `
  --api openai --model-url http://127.0.0.1:8000/v1 `
  --model-name unsloth/Qwen3.5-4B-GGUF:UD-Q6_K_XL --no-key
```

每条手动脚本在成功时退出码为 0，失败时为 1；可紧接着读取 `$LASTEXITCODE`。离线回归的测试总数会随代码变化，判断依据是**零失败**。手动脚本输出单行 JSON，不包含密钥或原始模型回复。

## 3. 怎样判定 JSON 结果

| 入口 | 必须观察到的结果 |
| --- | --- |
| `team_real_model_smoke` | 顶层 `status=passed`；至少一个 `model_responses`；`completion_tool_called=true`、`task_status=completed`、`owner_matches=true`、`member_state=idle`、`released=true`。 |
| `team_real_model_acceptance` | 顶层及 `LIVE-01`、`LIVE-02`、`LIVE-03` 全为 `status=passed`；每项 `model_responses>0`、`required_tools_executed=true`、`released=true`。 |
| `LIVE-01` | `message_verified=true`；两项任务为 `completed`，owner 分别是不同成员，成员均为 `idle`。 |
| `LIVE-02` | `resume_verified=true`；首次 `initial_teardown_failure_types` 含 `StopPendingTaskError`，最终 owner 不变、任务完成并释放。 |
| `LIVE-03` | `handoff_verified=true`；首次 teardown 同样部分失败，最终 owner 为新成员、旧成员为 `failed`、新成员为 `idle`，任务完成并释放。 |

`LIVE-02/03` 首轮只开放 `get_team_task`、限制为 1 turn，故意留下未完成任务；`LIVE-03` 再显式报告受控 fatal。它们验证**恢复路径**，不表示模型或服务自然发生故障。每名成员正常执行轮最多 6 turn，每次模型请求最多 512 输出 token。三个场景各用独立临时 workspace，脚本结束后自动清理。

若 `category` 非空，按实际结果排查：`service_or_protocol_error` 先查服务/协议；`model_no_response` 查模型回复；`model_no_required_tool` 查模型是否调用了符合参数要求的工具；`state_or_tool_result_mismatch` 查工具结果、owner、任务和成员状态；`teardown_failure` 查未完成任务或释放错误。**任务显示完成但消息内容错误，也不能算 `LIVE-01` 通过。** 不把失败重跑后的成功伪装成首次通过；记录两次结果及改动。

## 4. 单独检查交互式 Master

脚本化场景通过后，可在临时工作目录启动真正的 CLI，让模型自行选择 Master 工具。此检查是体验记录，不替代上面的脚本化门槛，也避免把运行文件写入项目工作树。

```powershell
$repoRoot = (Get-Location).Path
$caseDir = Join-Path ([IO.Path]::GetTempPath()) ('lite-team-cli-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $caseDir | Out-Null
Push-Location $caseDir
try {
  & (Join-Path $repoRoot '.venv\Scripts\python.exe') -B (Join-Path $repoRoot 'main.py') `
    --api openai --model_url http://127.0.0.1:8000/v1 `
    --api_key no-key --model_name unsloth/Qwen3.5-4B-GGUF:UD-Q6_K_XL `
    --ctx_tokens 8192
} finally {
  Pop-Location
}
```

在 `>>` 提示符可粘贴：

> 这是本地验收。不要调用 bash 或文件编辑工具。请创建名为 cli_worker 的 TeamAgent，创建一项描述为“只需调用 complete_team_task，无需文件或命令”的团队任务，分配给该成员，再用 get_team_task 和 get_team_member 核对实际任务 ID、成员 ID、任务状态和成员状态。不要调用 teardown_team，等我输入 q。

以**工具输出**确认 `assign_team_task` 为 `completed`、`get_team_task` 的 owner 正确且状态为 `completed`、`get_team_member` 为 `idle`；模型最后的自然语言总结不能代替这些证据。输入 `q`，进程正常退出表示团队已安全释放；若仍有未完成任务，CLI 会报告原因并保留会话。记录退出码与脱敏结果后，可删除本次创建的 `$caseDir` 临时目录。

## 5. 记录什么

记录 Git 提交号、模型 ID、服务地址、运行命令、退出码、脱敏 JSON 和失败分类；不要保存访问令牌或原始模型回复。TASK-09 当时的单次实测、首轮失败及修正后结果见[完成报告](<../features/agent team/_history/TASK-09_completion.md>)与[已接受审阅](<../features/agent team/_history/TASK-09_completion-review.md>)。新服务或模型应重新跑完整顺序。
