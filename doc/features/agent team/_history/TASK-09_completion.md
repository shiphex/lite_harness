# TASK-09 Completion Report

Status: Archived / Non-authoritative

Task: TASK-09 Extended Real-model Runtime Acceptance

Baseline: `ccee916` (`feature/team`)，开始时暂存区与工作区干净；下列实现与文档目前是未提交的工作树证据

Outcome: Implementation and local-model execution verified; pending completion review

Source of Truth: [07 测试计划](../07_test_plan.md) §1.4 / §4.6、[08 当前任务](../08_tasks.md) TASK-09；设计接受依据见 [TASK-09_human-review.md](TASK-09_human-review.md)

## 实际改动

- `scripts/team_real_model_acceptance.py` 新增只在显式调用时连接模型的入口，沿用现有 smoke 的配置解析。三项场景各自建立临时 workspace，以真实 TeamRuntime、Master bound 工具、TeamAgent 和统一 query_loop 执行；Master 工具由脚本驱动。
- 成员工厂仅为验收限制可见工具与执行预算，不替换 RuntimeFactory 或 query_loop。入口逐次封顶 512 输出 token、每轮最多 6 turn，观察 ToolExecutor 的**实际结果**，再核对 TaskStore、MemberRegistry、交接记录和 teardown。各场景输出脱敏 JSON、失败类别及模型请求/响应数；只要一项失败，入口退出码为 1。
- `tests/team/test_real_model_acceptance.py` 以离线 adapter 验证三场景完整路径，以及纯文字回复、错误任务 ID、teardown 失败和场景异常后的释放尝试。默认 pytest 不请求真实模型。
- `07_test_plan.md` 登记 `LIVE-01～03` 与追踪行，`08_tasks.md` 登记 TASK-09；完成审阅接受前均保持 `[ ]`。

## 验证证据

| 命令或检查 | 实际结果 |
| --- | --- |
| `GET http://127.0.0.1:8000/health`、`GET http://127.0.0.1:8000/v1/models` | `status=ok`；模型 ID 为 `unsloth/Qwen3.5-4B-GGUF:UD-Q6_K_XL`。 |
| `.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider tests/team/test_real_model_acceptance.py` | 4 passed。测试先行时曾因新入口不存在失败；实现过程中工具观察器参数错误和异常后未尝试释放的问题被测试发现并修复。 |
| `.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider` | 374 passed in 4.58s；无真实模型请求。 |
| `.venv/Scripts/python.exe -B -m scripts.team_real_model_smoke --api openai --model-url http://127.0.0.1:8000/v1 --model-name unsloth/Qwen3.5-4B-GGUF:UD-Q6_K_XL --no-key` | Exit 0；`status=passed`，2 requests / 2 responses，任务 `completed`、成员 `idle`、`released=true`。 |
| `.venv/Scripts/python.exe -B -m scripts.team_real_model_acceptance --api openai --model-url http://127.0.0.1:8000/v1 --model-name unsloth/Qwen3.5-4B-GGUF:UD-Q6_K_XL --no-key` | 首轮 Exit 1：`LIVE-01` 发送了场景标签而非指定令牌，脚本拒绝误判；明确消息参数后及审查修复后实跑均 Exit 0。最终一次三个场景均 `passed`，请求/响应数依次为 6/6、3/3、3/3，且全部 `released=true`；`LIVE-02/03` 的首次部分 teardown 均记录 `StopPendingTaskError`。 |
| 在临时目录以仓库中 Python 与 `main.py` 的绝对路径启动，参数为 `--api openai --model_url http://127.0.0.1:8000/v1 --api_key no-key --model_name unsloth/Qwen3.5-4B-GGUF:UD-Q6_K_XL --ctx_tokens 8192` | 交互式 Master 实际调用 spawn、create、assign、get task、get member；任务 `task_a15b7459` 为 `completed`，成员 `cli_worker-c38efa3e` 为 `idle`；输入 `q` 后 Exit 0。此项单列体验记录。 |
| `git diff --check` | Exit 0；未发现空白错误。 |

## 边界、风险与交接

- `LIVE-02/03` 的未完成首轮和 `LIVE-03` fatal 由测试受控构造；真实模型负责后续完成工具选择。没有观测真实模型或服务自行发生 fatal。
- 本轮仅验证当前本地模型与 OpenAI-compatible 服务。首次 `LIVE-01` 的错误参数表明模型输出可能受描述措辞影响；验收以实际工具结果和状态为准，不靠自然语言回复或自动重试掩盖失败。
- 临时 workspace 中的任务文件不作为持久证据；报告只保留命令与聚合状态，不包含 Hugging Face 令牌、模型 API 凭据或原始模型回复。
- 下一门槛为 [Human_Review.md](../Human_Review.md) 的完成审阅。审阅接受前 `LIVE-01～03`、追踪行与 Optional Live Acceptance 继续为 `[ ]`；尚未执行暂存或提交。
