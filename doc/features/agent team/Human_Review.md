# TASK-08 Completion Review

Status: Accepted Review

Task: TASK-08 Optional Real-model E2E Smoke

Based on: [_history/TASK-08_completion.md](_history/TASK-08_completion.md)

Result: 用户接受 TASK-08 的实现范围、运行边界及本地真实模型实测结果；随后已明确授权限定文件的结束提交，提交完成前任务暂留当前任务区。

Reviewer: User（2026-10-01 对完成审阅稿明确回复“同意”）

Design authority: [已接受的设计审阅](_history/TASK-08_human-review.md)；DD-01～DD-03 均已接受

Superseded by: [测试计划](07_test_plan.md) SMOKE-01、[当前任务](08_tasks.md) TASK-08；本审阅的归档副本见 [_history/TASK-08_completion-review.md](_history/TASK-08_completion-review.md)

Prepared by: Codex

Baseline: `a87ba3624622b083cabb34da35960e4f6db23637` (`feature/team`)；本轮实现尚未暂存或提交

## 待审范围与依据

- [完成报告](_history/TASK-08_completion.md)记录入口、离线测试、真实模型命令及聚合结果。
- [smoke 入口](../../../scripts/team_real_model_smoke.py)只在显式调用时连接模型。Master bound 工具由脚本驱动，TeamAgent 通过既有统一 `query_loop` 调用真实模型；临时 workspace 中只有一名成员和一个任务。
- 入口要求显式 API、URL、模型名及鉴权模式；环境变量提供真实密钥，单次最多 3 turn、每次请求最多 512 输出 token。本次实际仅暴露 `get_team_task` 与 `complete_team_task` 两项工具。
- [离线测试](../../../tests/team/test_real_model_smoke.py)覆盖成功、未完成、凭据配置、URL 凭据拒绝、服务错误隐藏敏感信息及运行时失败分类。全量 pytest：370 passed。默认回归没有真实模型请求。
- 本地 llama.cpp 真实运行：2 次模型请求、2 次响应、2 turn；模型调用当前任务的 `complete_team_task`；TaskStore 为 `completed` 且 owner 正确；成员返回 IDLE；teardown 最终释放，无失败类型。

## 完成审阅裁决

1. **实现范围：接受。** 脚本验证 DD-01 约定的 Master 工具到真实 TeamAgent loop 的组合；Master 自身的模型决策不在此项覆盖内。
2. **边界与安全：接受。** DD-02 的显式启动、临时 workspace、任务数、turn 和 token 限额、凭据来源及不回显均有实现与验证。
3. **实测结果：接受。** DD-03 的真实模型工具调用、任务 owner / completed、成员 IDLE 与 release 均有单次运行证据；失败路径保留分类，未把未完成或跳过记为通过。
4. **剩余风险：** 只实测当前本地 OpenAI-compatible 服务与模型；其他服务、模型和网络环境需各自运行。临时任务文件运行后清理，完成报告保留聚合结果。

## 审阅后交接

完成审阅已接受；原提案中的覆盖边界与剩余风险一并记录。[测试计划](07_test_plan.md)的 `SMOKE-01` 与追踪行、[任务清单](08_tasks.md)的 Optional Smoke Phase 已按接受和实测证据标记 `[√]`。用户在后续回复明确授权仅暂存并提交 TASK-08 的七个改动文件；结束提交后按 SDD 规则更新任务交接。
