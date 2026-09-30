# TASK-06 Recovery Design Review

Status: Accepted Review

Task: TASK-06 Shutdown / Teardown / Failure Closure

Based on: [TASK-06_completion.md](TASK-06_completion.md) CR-02

Result: 用户接受 CR-01 的现有实现，并要求 CR-02 在 FAILED 成员持有未完成任务时由 Master 显式请求创建全新 TeamAgent 执行；CR-03 的完成验收勾选仍待实施后审阅。

Superseded by: updated [`../02_architecture.md`](../02_architecture.md)、[`../03_runtime.md`](../03_runtime.md)、[`../04_contracts.md`](../04_contracts.md)、[`../05_failures.md`](../05_failures.md)、[`../06_decisions.md`](../06_decisions.md)、[`../07_test_plan.md`](../07_test_plan.md)、[`../08_tasks.md`](../08_tasks.md)

Reviewer: 用户（明确拒绝让现有 IDLE 成员接手，并批准新成员恢复计划）

Prepared by: Codex

## 裁决

- 每次恢复由 Master 指定一项 FAILED owner 的 `in_progress` 任务；系统创建名称为 `recovery_<task_id>` 的全新 TeamAgent，并立即同步执行一轮。现有 IDLE 成员与其上下文不参与。
- 保留任务 ID、状态和依赖；TaskStore 按顺序保存原 owner、新 owner 与 `source_failed` 交接原因。旧任务文件仍可加载。
- 新成员使用任务内容及共享工作区，不复制失败成员的聊天历史。交接前失败保留原 owner；交接后失败保留新 owner 与可续跑入口。
- CR-03 只是完成审阅后的状态记录：本次设计接受不勾选 Phase 5、SC-04～07 或新增测试项。
