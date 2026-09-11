# 总体任务列表

1. MVP:

   - Existing Code Gap Analysis
   - Team Core Contract Implementation & Composition
   - Spawn Vertical Slice
   - Messaging Vertical Slice
   - Task Collaboration
   - Shutdown / Teardown / Failure Closure
   - Integration / Architecture Enforcement
2. Optional:

   - Optional Real-model E2E Smoke

Optional Real-model E2E Smoke 在 Phase 6 完成后执行，不阻塞 MVP。

| Phase   | 目的    | 典型验证 | 对应任务 |
| ------- | ------- | ------- | ------- |
| Phase 0 | Existing Code Gap Analysis       | Spec 与现有 Runtime/Task/Tool 对齐            | Existing Code Gap Analysis |
| Phase 1 | Team contract implementation / composition | 落实已接受的 Contract，TeamRuntime 建立共享服务 | Team Core Contract Implementation & Composition |
| Phase 2 | Spawn vertical slice             | Master → Coordinator → Lifecycle → Registry  | Spawn Vertical Slice |
| Phase 3 | Messaging vertical slice         | TeamAgent → MailboxHandle → MessageBus       | Messaging Vertical Slice |
| Phase 4 | Task collaboration               | MasterAgent + existing TaskStore + TeamAgent | Task Collaboration |
| Phase 5 | Shutdown / teardown / failures   | 生命周期和 rollback 闭环                      | Shutdown / Teardown / Failure Closure |
| Phase 6 | Integration / architecture enforcement | SC、ARCH、Failure tests                | Integration / Architecture Enforcement |


# Current Facts

> TASK-01 已使用独立代码证据验证下列事实，Human Review 已接受验证结果。

Validated against: `f90561fff98dcc86ec4261b38e6c32f04c9a9f96`

| ID | Status | Confirmed code fact | Evidence |
| --- | --- | --- | --- |
| CF-01 | `confirmed` | `AgentRuntime` 已存在。 | `f90561f/core/runtime.py:113` |
| CF-02 | `confirmed` | 当前 MasterAgent 和 Subagent 均通过 `query_loop` 执行。 | `f90561f/core/agent.py:147`、`f90561f/tools/subagent.py:167` |
| CF-03 | `confirmed` | `task_system` 已使用 JSON 持久化任务。 | `f90561f/tools/task_system.py:96`、`f90561f/tools/task_system.py:195`、`f90561f/tools/task_system.py:206` |
| CF-04 | `confirmed` | `claim_task` / `complete_task` 已存在，但当前是绑定模块级全局 `TASKS` 的函数，尚未形成可直接注入 TeamRuntime 的实例协议。 | `f90561f/tools/task_system.py:243`、`f90561f/tools/task_system.py:330`、`f90561f/tools/task_system.py:352` |
| CF-05 | `confirmed` | 当前目标分支中未发现 team-level member registry。 | `f90561f` repository tree；`MemberRegistry` symbol search：no matches |
| CF-06 | `confirmed` | 当前目标分支中未发现 mailbox abstraction。 | `f90561f` symbol search；`MailboxHandle` / `MessageBus`：no matches |

## Accepted Design Constraints

| ID | Constraint | Source |
| --- | --- | --- |
| DC-01 | TeamAgent 复用现有 `AgentRuntime`，不新建一套 TeamAgentRuntime。 | `01_problem.md` §2.1、`02_architecture.md` §2.2 |
| DC-02 | TeamAgent 必须通过统一 `query_loop` 执行。 | `01_problem.md` SC-02、`07_test_plan.md` ARCH-04 |
| DC-03 | TeamRuntime 是独立于 AgentRuntime 的 team composition root，负责组装并持有 team-scoped shared services；具体代码落点不是架构约束。 | `02_architecture.md` §2.1、`06_decisions.md` ADR-001 |
| DC-04 | MemberRegistry 是 MemberState 的唯一 authoritative owner；所有状态变化经过受控转换入口，STOPPED / FAILED record 保留到 TeamRuntime 最终释放。 | `02_architecture.md` §2.4～2.5、`03_runtime.md` §1.2、`04_contracts.md` §2.5、`06_decisions.md` ADR-002 |
| DC-05 | 每个 TeamRuntime 使用独立的现有 TaskStore；Team 路径采用显式 store 注入，不复制任务逻辑，并保持全局 `TASKS` 工具路径兼容。 | `02_architecture.md` §2.1、`04_contracts.md` §2.2 / §3.2、`06_decisions.md` ADR-003 |
| DC-06 | 设计和测试引用现有 runtime factory 时使用实际符号 `RuntimeFactory`。 | `f90561f/core/runtime.py:143`、`07_test_plan.md` ARCH-01 |


# Completed Tasks

## TASK-01 Existing Code Gap Analysis

Status: Done

Baseline: `f90561fff98dcc86ec4261b38e6c32f04c9a9f96`

Outcome:

- CF-01～CF-06 confirmed。
- DD-01～DD-04 reviewed and adjudicated。
- Phase 1: GO。

Decision references:

- `02_architecture.md` §2.1、§2.4～2.5
- `03_runtime.md` §1.1～1.3
- `04_contracts.md` §2.2、§2.5、§3.2
- `05_failures.md` §1～§2
- `06_decisions.md` ADR-001～ADR-003
- `07_test_plan.md` STATE-04～STATE-07、F-STATE-01、ARCH-01 / ARCH-05 / ARCH-06、STORE-01 / STORE-02、REGISTRY-01 / REGISTRY-02

History:

- [TASK-01 Gap Analysis](_history/TASK-01_gap-analysis.md)
- [TASK-01 Human Review](_history/TASK-01_human-review.md)
