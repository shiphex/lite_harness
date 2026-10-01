# TASK-08 Completion Report

Status: Archived / Non-authoritative

Task: TASK-08 Optional Real-model E2E Smoke

Baseline: `a87ba3624622b083cabb34da35960e4f6db23637` (`feature/team`)，本轮开始时暂存区与工作区干净；下列实现和文档为尚未提交的工作树证据

Outcome: Implementation and live smoke verified; pending independent completion review

Source of Truth: [`../07_test_plan.md`](../07_test_plan.md) §1.3 / §4.5、[`../08_tasks.md`](../08_tasks.md) TASK-08；设计裁决见 [TASK-08_human-review.md](TASK-08_human-review.md)

## 实际改动

- `scripts/team_real_model_smoke.py` 增加仅手动运行的入口。调用者必须给出 API、URL、模型名及 `--no-key` 或 `--api-key-env`；真实密钥仅从环境变量读取，URL 不允许 userinfo、query 或 fragment。脚本输出只含分类与状态，不含密钥或原始模型响应。
- 入口在临时 workspace 中用 `RuntimeFactory` 创建 Master runtime 和真实 `TeamRuntime`，通过 Master bound 工具创建一名 TeamAgent、一项任务并同步分配。真实模型只驱动 TeamAgent 既有 `query_loop`。本次 smoke 可见工具仅为 `get_team_task`、`complete_team_task`，不修改生产团队契约。
- 单次 TeamAgent 最多 3 turn；适配器请求逐次封顶 512 输出 token，包括既有输出截断恢复路径。结果核对真实模型响应触发的当前任务完成工具、TaskStore owner / `completed`、成员 IDLE 及最终 release。失败类别区分配置/凭据、服务或协议、模型未调用完成工具、任务或成员状态、执行和 teardown；报告 teardown 失败类型。
- `tests/team/test_real_model_smoke.py` 增加 6 项离线验证，替换的只有外部模型适配器；真实 `query_loop`、工具、任务存储和生命周期仍参与测试。默认 pytest 不连接模型服务。

## 验证证据

| 命令或检查 | 实际结果 |
| --- | --- |
| `.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider tests/team/test_real_model_smoke.py` | 6 passed；测试先行过程中分别观察到缺入口、URL 凭据拒绝、服务分类、工具收敛与 teardown 类型的预期失败，再实现至通过。 |
| `.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider` | 370 passed in 4.59s，未发起真实模型请求。 |
| `GET http://127.0.0.1:8000/health`、`GET http://127.0.0.1:8000/v1/models` | HTTP 200；模型 ID 为 `unsloth/Qwen3.5-4B-GGUF:UD-Q6_K_XL`。 |
| `.venv/Scripts/python.exe -B -m scripts.team_real_model_smoke --api openai --model-url http://127.0.0.1:8000/v1 --model-name unsloth/Qwen3.5-4B-GGUF:UD-Q6_K_XL --no-key` | Exit 0，`status=passed`；2 requests / 2 responses / 2 turns；`completion_tool_called=true`、`task_status=completed`、`owner_matches=true`、`member_state=idle`、`released=true`、`teardown_failure_types=[]`。 |

上述真实运行是单次手动调用，使用本地无鉴权占位值 `no-key`。临时 workspace 在运行结束后自动清理；报告保留不含密钥的聚合证据，任务文件不作为持久验收产物。

## 边界与审阅

- Master bound 工具由脚本驱动；未验证模型自行决定 Master 的 spawn / assign。模型实际调用只覆盖 TeamAgent 的统一 loop 与 OpenAI-compatible 适配器。
- 本地服务与模型的成功不推广为其他服务的兼容性。429/529 的既有重试行为没有修改；本轮真实调用未观察到重试。
- 尚未收到独立完成审阅的接受结论，也没有 TASK-08 结束提交。`SMOKE-01`、Optional Smoke Phase 与追踪行保持 `[ ]`，TASK-08 留在当前任务区。下一门槛为 [`../Human_Review.md`](../Human_Review.md) 的完成审阅；通过后按项目规则处理结束提交与阶段交接。
