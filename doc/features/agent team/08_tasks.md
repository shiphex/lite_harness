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

| status | Phase   | 目的    | 典型验证 | 对应任务 |
| ------- | ------- | ------- | ------- | ------- |
| [√] | Phase 0 | Existing Code Gap Analysis       | Spec 与现有 Runtime/Task/Tool 对齐            | Existing Code Gap Analysis |
| [√] | Phase 1 | Team contract implementation / composition | 落实已接受的 Contract，TeamRuntime 建立共享服务 | Team Core Contract Implementation & Composition |
| [√] | Phase 2 | Spawn vertical slice             | Master → Coordinator → Lifecycle → Registry  | Spawn Vertical Slice |
| [√] | Phase 3 | Messaging vertical slice         | TeamAgent → MailboxHandle → MessageBus       | Messaging Vertical Slice |
| [√] | Phase 4 | Task collaboration               | MasterAgent + existing TaskStore + TeamAgent | Task Collaboration |
| [ ] | Phase 5 | Shutdown / teardown / failures   | 生命周期和 rollback 闭环                      | Shutdown / Teardown / Failure Closure |
| [ ] | Phase 6 | Integration / architecture enforcement | SC、ARCH、Failure tests                | Integration / Architecture Enforcement |


# Current Facts

维护规则：切换当前任务时，只保留与该任务有关、且有验收证据的代码事实，目标约 7～8 条。

> 下列代码事实已通过 TASK-01～TASK-05 的对应审阅；TASK-05 的完成审阅见 [`_history/TASK-05_completion-review.md`](_history/TASK-05_completion-review.md)。

Validated against: CF-01～CF-03 为 `70825632e033e64778d5373d6d8da2b619a56ad8`；CF-04～CF-05 为 `fbed4f01d15fd0e48c30480d0104f731ec9437f9`；CF-06～CF-08 为 `0fbbbc3`。

| ID | Status | Confirmed code fact | Evidence |
| --- | --- | --- | --- |
| CF-01 | `confirmed` | `MemberRegistry` 是 MemberState 的 authoritative owner，状态变化由受控 `transition()` 应用。 | `7082563/team/registry.py:65`、`7082563/team/registry.py:138` |
| CF-02 | `confirmed` | 每个 TeamRuntime 拥有独立 TaskStore；现有 task-system operation 可显式注入 store，未注入时沿用全局 `TASKS`。 | `7082563/team/runtime.py:28`、`7082563/tools/task_system.py:247` |
| CF-03 | `confirmed` | TeamRuntime 已组装 Registry、MessageBus、TaskStore、LifecycleManager 与 Coordinator。 | `7082563/team/runtime.py:14`、`7082563/team/runtime.py:23` |
| CF-04 | `confirmed` | Master session 创建 sibling TeamRuntime，并仅向 Master 实例绑定 spawn 与团队任务工具。 | `fbed4f0/core/agent.py:125`、`fbed4f0/core/agent.py:136`、`fbed4f0/tools/team.py:12` |
| CF-05 | `confirmed` | TeamCoordinator 编排 spawn、team-scoped 任务创建/查询，以及显式分配和原 owner 续跑；领取复用现有 task_system。 | `fbed4f0/team/coordinator.py:30`、`fbed4f0/team/coordinator.py:61`、`fbed4f0/team/coordinator.py:74` |
| CF-06 | `confirmed` | LifecycleManager 持有已发布 TeamAgent，并以实际 runtime ID 绑定 mailbox handle；可通过 `get_agent()` 只读查询 wrapper。 | `0fbbbc3/team/lifecycle.py:85`、`0fbbbc3/team/lifecycle.py:111` |
| CF-07 | `confirmed` | TeamAgent 的 `run(prompt)` 仍进入统一 `query_loop`；消息收发本身不启动执行。 | `0fbbbc3/team/agent.py:36`、`0fbbbc3/team/messaging.py:36` |
| CF-08 | `confirmed` | MessageBus 已提供 team-scoped 收发；TeamAgent 专属消息工具通过 `ToolContext.runtime` 验证并使用绑定的 handle。 | `0fbbbc3/team/messaging.py:43`、`0fbbbc3/team/messaging_tools.py:44` |

## Accepted Design Constraints

维护规则：只摘要约 7～8 条跨阶段约束；除重大方向或理念变更外，不随普通任务进度改写。

| ID | Constraint | Source |
| --- | --- | --- |
| DC-01 | TeamAgent 复用现有 `AgentRuntime` 与统一 `query_loop`，不新建 TeamAgentRuntime 或第二套 loop。 | `01_problem.md` §2.1 / SC-02、`02_architecture.md` §2.2、`07_test_plan.md` ARCH-04 |
| DC-02 | TeamRuntime 独立于 AgentRuntime，组装并持有 team-scoped shared services；一个 Master session 对应一个 sibling TeamRuntime，共享显式 session_id，并通过 Master-only bound handler 连接。具体代码落点不是架构约束。 | `02_architecture.md` §2.1、`06_decisions.md` ADR-001 / ADR-008 |
| DC-03 | MemberRegistry 是 MemberState 的唯一 authoritative owner；所有状态变化经过受控转换入口，STOPPED / FAILED record 保留到 TeamRuntime 最终释放。 | `02_architecture.md` §2.4～2.5、`03_runtime.md` §1.2、`04_contracts.md` §2.5、`06_decisions.md` ADR-002 |
| DC-04 | 每个 TeamRuntime 使用独立的现有 TaskStore；Team 路径采用显式 store 注入，不复制任务逻辑，并保持全局 `TASKS` 工具路径兼容。 | `02_architecture.md` §2.1、`04_contracts.md` §2.2 / §3.2、`06_decisions.md` ADR-003 |
| DC-05 | MessageBus 管理 team-scoped mailbox storage；Agent 只通过自身的 MailboxHandle 使用收发能力，不直接持有或修改 mailbox。 | `02_architecture.md` §2.3、`04_contracts.md` §2.1 / §2.3、`06_decisions.md` ADR-004 |
| DC-06 | 消息执行语义采用 one-message-one-turn；Phase 3 只落实收发边界，不据此启动 TeamAgent 执行。 | `06_decisions.md` ADR-006、`03_runtime.md` §1.1 / §1.4 |
| DC-07 | Spawn 只发布被动 TeamAgent wrapper，IDLE 是 commit；只有 LifecycleManager 通过实际符号 `RuntimeFactory` 创建并逻辑持有 TeamAgent runtime/wrapper，commit 前逆序 rollback，不承诺删除 runtime diagnostic artifacts。 | `06_decisions.md` ADR-007 / ADR-010、`f90561f/core/runtime.py:143`、`07_test_plan.md` ARCH-01 |
| DC-08 | TeamAgent 有独立 runtime/state/history/identity；Phase 2 的只读 execution policy 是 provisional mechanism。 | `06_decisions.md` ADR-009 |


# Next Gate

TASK-05 / Phase 4 已完成验收，证据见 [`_history/TASK-05_completion.md`](_history/TASK-05_completion.md) 与 [`_history/TASK-05_completion-review.md`](_history/TASK-05_completion-review.md)。下一道门槛是 TASK-06 Shutdown / Teardown / Failure Closure 的预检；尚未启动 TASK-06，也未勾选 Phase 5。

# Completed Tasks

| Task | Outcome | End commit | History |
|---|---|---|---|
| TASK-01 Existing Code Gap Analysis | Done / Phase1 GO | `f90561fff98dcc86ec4261b38e6c32f04c9a9f96` | _history/TASK-01_*.md |
| TASK-02 Team Core Contract Implementation & Composition | Done / Phase 1 complete | `70825632e033e64778d5373d6d8da2b619a56ad8` | _history/TASK-02_*.md |
| TASK-03 Spawn Vertical Slice | Done / Phase 2 complete | `f8c76c4611e582e99245c9638f3dc5206db3e868` | _history/TASK-03_*.md |
| TASK-04 Messaging Vertical Slice | Done / Phase 3 complete | `b007aa4be943ed6fa6ebade27b7f08a18cd94076` | _history/TASK-04_*.md |
| TASK-05 Task Collaboration | Done / Phase 4 complete | `fbed4f01d15fd0e48c30480d0104f731ec9437f9` | [Completion report](_history/TASK-05_completion.md) / [Accepted review](_history/TASK-05_completion-review.md) |
