# TASK-06 Design Review

Status: Accepted Review

Task: TASK-06 Shutdown / Teardown / Failure Closure

Based on: [TASK-06_preflight.md](TASK-06_preflight.md)

Result: 用户接受 DD-01、DD-03～DD-06，并将 DD-02 修订为有活动执行或未完成/待修复任务时拒绝停止；正常 `q/exit` 遇此情况也拒绝退出。TASK-06 设计已接受，实施及 Phase 5 完成验收仍未完成。

Superseded by: updated [`02_architecture.md`](../02_architecture.md)、[`03_runtime.md`](../03_runtime.md)、[`04_contracts.md`](../04_contracts.md)、[`05_failures.md`](../05_failures.md)、[`06_decisions.md`](../06_decisions.md)、[`07_test_plan.md`](../07_test_plan.md)、[`08_tasks.md`](../08_tasks.md)

Reviewer: 用户（逐项指示 DD-02 禁止遗留不可续跑任务、其余提案同意，并选择正常退出时拒绝退出）

Prepared by: Codex

## 审阅依据

- TASK-05 已完成验收并归档，见 [TASK-05_completion-review.md](TASK-05_completion-review.md)。当前 HEAD 为 `506e185a33e2c9346e30a166f0b7aa3b03ec99dd`，预检开始时工作区干净；本轮回归为 309 passed。
- `01_problem.md` §2.1 / SC-04、SC-05，`02_architecture.md` §2.3～2.6，`03_runtime.md` §1.2，`04_contracts.md` §2.4～2.5，`05_failures.md` F-STOP-01，ADR-002/005/010 共同定义生命周期边界、终态可观察性和失败政策。
- 当前 `LifecycleManager` 只实现 spawn 与 rollback；TeamCoordinator 同步执行任务，MessageBus 的状态检查与 Registry transition 尚未共享并发顺序。具体证据和建议见预检报告。
- 用户本轮明确要求：DD-02 不允许停止后留下不可续跑的任务。现有 TaskStore 只有领取和原 owner 完成路径，TeamCoordinator 只允许原 owner 续跑；当前没有任务取消或重新分配入口。预检报告保留原提案作为历史证据，以下 DD-02 行是修订建议。
- 用户随后表示“其他的同意”，接受 DD-01、DD-03～DD-06；对正常 `q/exit` 明确选择“拒绝退出，完成恢复后再退出”。

## 待裁决设计差异

| ID | Codex 建议 | 请裁决的关键点 | 结论 |
| --- | --- | --- | --- |
| DD-01 入口与结果 | Master 专属停止/teardown 入口；LifecycleManager 独占 wrapper 停止，Registry 保留终态；正常 `q/exit` 调用 teardown，失败则报告并保留会话。 | 退出处理遵循 DD-02；不虚报最终释放。 | 已接受 |
| DD-02 执行中停止 | 活动 turn 返回 `StopBusyError`；成员仍拥有 `in_progress` 任务，或任务已完成但成员收尾转换未恢复时，拒绝停止并保留 wrapper / Registry 状态。Master 先用原 owner 的 `resume_team_task` 完成或修复状态，之后重试停止；不自动重置或改派任务。teardown 遇此情况报告部分失败且不最终释放，正常 `q/exit` 拒绝退出。 | 不允许停止或正常退出后留下不可续跑任务。 | 按用户修订接受 |
| DD-03 fatal | 普通执行异常保留 TASK-05 的续跑语义；显式确认不可恢复的 runtime 故障才转 FAILED，并保留错误与任务事实。 | 不自动将一次普通执行异常归类为 fatal。 | 已接受 |
| DD-04 teardown | 逐成员 best-effort 停止并汇总；有失败则保留 team 和终态记录供重试；全部安全停止后最终释放内存记录与 mailbox，任务文件保留。 | 与 DD-02 联动：未完成任务导致停止被拒绝时不得最终释放。 | 已接受 |
| DD-05 消息竞态 | 消息收发与停止/fatal transition 共用顺序边界；转换之后拒绝收发，已接受消息保留到最终释放。 | 保持 Registry / MessageBus 各自所有权。 | 已接受 |
| DD-06 F-STOP-01 | 将旧“worker 强制清理”表述适配无后台 worker 的同步执行；活动 turn 返回忙碌，fatal 转 FAILED。 | 不引入不存在的 runtime 强制关闭能力。 | 已接受 |

## 拟议审阅结果

**APPROVE（设计）**：将上述裁决传播到权威规格、ADR、测试追踪和任务状态；新增测试与 Phase 5 均保持未完成。实施后还需独立 Completion Report 和完成审阅，不能以本次设计接受替代验收。
