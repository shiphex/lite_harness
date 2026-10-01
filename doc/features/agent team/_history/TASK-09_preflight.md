# TASK-09 Preflight

Status: Archived / Non-authoritative

Task: TASK-09 Extended Real-model Runtime Acceptance

Baseline: `ccee916` (`feature/team`)，开始时暂存区与工作区干净

Outcome: Ready；用户提供并要求实施完整的运行测试方案

Source of Truth: [07 测试计划](../07_test_plan.md) §1.3 / §1.4 / §4.6、[08 当前任务](../08_tasks.md) TASK-09；既有设计来自 `01_problem.md`～`06_decisions.md`

## 当前事实与拟改动

- TASK-08 已完成并接受；`scripts/team_real_model_smoke.py` 仅覆盖一名成员完成一项任务，Master bound 工具由脚本驱动。基线全量 pytest 为 370 passed，既有真实模型 smoke 返回 `status=passed`，且未修改跟踪文件。
- 本地 `GET /health` 为 `{"status":"ok"}`，`GET /v1/models` 返回 `unsloth/Qwen3.5-4B-GGUF:UD-Q6_K_XL`。服务经现有 OpenAI adapter 使用 `http://127.0.0.1:8000/v1` 与本地 `no-key` 占位值。
- 新增独立、显式的 `LIVE-01～03` 入口及离线防误判测试；在 `07` / `08` 登记新检查项和任务，提供交互式 Master 的独立体验记录。产品运行时公开契约不变，默认 pytest 不请求模型。

## 裁决与边界

- 用户选择“完整闭环”范围，并选择交互式 Master 单列体验验收；随后提供正式方案并明确要求实现。脚本化三场景全部通过才是扩展运行验收通过。
- `LIVE-02/03` 首轮受控限制工具与 turn；`LIVE-03` fatal 为显式注入，不得解释为模型或服务自然故障。
- 每场景独立临时 workspace、每名成员每轮最多 6 turn、每次模型请求最多 512 输出 token。保存脱敏聚合状态，不保存密钥或原始模型回复。

## 验证计划与门槛

先运行离线测试的缺入口失败，再实现并运行针对性测试；随后检查服务与模型 ID、全量 pytest、既有 smoke、新 `LIVE-01～03`，最后在临时目录做交互式 Master 检查。任何缺少所需工具执行、状态不符或最终未释放均不得标记通过。完成报告和审阅接受前，新检查项保持 `[ ]`。
