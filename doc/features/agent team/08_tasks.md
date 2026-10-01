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
   - Extended Real-model Runtime Acceptance

Optional Real-model E2E Smoke 在 Phase 6 完成后执行，不阻塞 MVP。

| status | Phase   | 目的    | 典型验证 | 对应任务 |
| ------- | ------- | ------- | ------- | ------- |
| [√] | Phase 0 | Existing Code Gap Analysis       | Spec 与现有 Runtime/Task/Tool 对齐            | Existing Code Gap Analysis |
| [√] | Phase 1 | Team contract implementation / composition | 落实已接受的 Contract，TeamRuntime 建立共享服务 | Team Core Contract Implementation & Composition |
| [√] | Phase 2 | Spawn vertical slice             | Master → Coordinator → Lifecycle → Registry  | Spawn Vertical Slice |
| [√] | Phase 3 | Messaging vertical slice         | TeamAgent → MailboxHandle → MessageBus       | Messaging Vertical Slice |
| [√] | Phase 4 | Task collaboration               | MasterAgent + existing TaskStore + TeamAgent | Task Collaboration |
| [√] | Phase 5 | Shutdown / teardown / failures   | 生命周期和 rollback 闭环                      | Shutdown / Teardown / Failure Closure |
| [√] | Phase 6 | Integration / architecture enforcement | SC、ARCH、Failure tests                | Integration / Architecture Enforcement |
| [√] | Optional Smoke | Real-model E2E smoke | 显式调用真实模型并核对团队任务闭环 | TASK-08 Optional Real-model E2E Smoke |
| [√] | Optional Live Acceptance | Extended real-model runtime acceptance | 双成员消息、续跑、FAILED 交接与交互式 Master 体验记录 | TASK-09 Extended Real-model Runtime Acceptance |


# Current Facts

维护规则：切换当前任务时，只保留与该任务有关、且有验收证据的代码事实，目标约 7～8 条。

> CF-01～07 于 TASK-08 预检时核对；CF-08 由 TASK-08 的实现提交和完成审阅确认。既有设计验收见 [`_history/`](./_history/README.md)。

Validated against: CF-01～07 的预检基线为 `4b575b6c437bdbbf3c82467ebf73b5099724caec`；CF-08 的实现提交为 `a440cef4c56764093f8ee66b6a279529595e059e` (`feature/team`)；全量 pytest 为 370 passed，证据见[预检](_history/TASK-08_preflight.md)、[完成报告](_history/TASK-08_completion.md)与[已接受审阅](_history/TASK-08_completion-review.md)。

| ID | Status | Confirmed code fact | Evidence |
| --- | --- | --- | --- |
| CF-01 | `confirmed` | TeamRuntime 组装并持有 Registry、MessageBus、独立 TaskStore、LifecycleManager 与 Coordinator。 | `eb9ed3b/team/runtime.py:27`～`:42` |
| CF-02 | `confirmed` | Master session 创建 sibling TeamRuntime，共享显式 session_id，并将团队工具绑定在 Master 实例。 | `eb9ed3b/core/agent.py:124`～`:137`、`eb9ed3b/tools/team.py:110` |
| CF-03 | `confirmed` | LifecycleManager 是 TeamAgent runtime 的创建入口，持有已发布 wrapper，并按实际 runtime ID 绑定 mailbox handle。 | `eb9ed3b/team/lifecycle.py:87`～`:135`、`:344` |
| CF-04 | `confirmed` | TeamAgent 的 `run(prompt)` 进入既有 `query_loop`；消息工具使用实际 runtime 身份取得绑定 handle。 | `eb9ed3b/team/agent.py:30`～`:58`、`eb9ed3b/team/messaging_tools.py:39`～`:70` |
| CF-05 | `confirmed` | 统一 query_loop 经 adapter factory 发出 ModelRequest；模型配置允许指定 API、URL、密钥与模型名，默认指向本地服务。 | `4b575b6/core/loop.py:455`～`:463`、`4b575b6/api/adapter_factory.py:12`、`4b575b6/config/config.py:62`～`:67` |
| CF-06 | `confirmed` | Team 路径复用显式注入的 TaskStore；未注入 store 的旧路径仍使用全局 `TASKS`。 | `eb9ed3b/team/coordinator.py:73`～`:82`、`eb9ed3b/tools/task_system.py:296`～`:303` |
| CF-07 | `confirmed` | Coordinator 编排分配、原 owner 续跑及 FAILED 任务显式恢复；任务交接由现有 task_system 保存。 | `eb9ed3b/team/coordinator.py:84`～`:109`、`:138`～`:184`、`eb9ed3b/tools/task_system.py:458` |
| CF-08 | `confirmed` | Phase 6 全链路测试仍使用 fake loop；TASK-08 增加独立、显式的真实模型 smoke 入口，本地单任务实测通过。 | `a440cef/tests/team/test_phase6_integration.py:1`、`a440cef/scripts/team_real_model_smoke.py:1`、`a440cef/tests/team/test_real_model_smoke.py:1`、[完成报告](_history/TASK-08_completion.md) |

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

TASK-09 的[完成审阅](Human_Review.md)已接受并归档，副本见[历史审阅](_history/TASK-09_completion-review.md)。`LIVE-01～03`、追踪行与 Optional Live Acceptance 已按实测证据标记 `[√]`；实现提交为 `dc958281fdd4b664c5de4696607c855cae36cb3d`，架构及运行说明提交为 `1b9b59d26172650599405f75170f5dd265bd25a9`。既有 MVP 与 TASK-08 状态不变；当前没有待执行任务，后续需求按新任务预检。

# Completed Tasks

| Task | Outcome | End commit | History |
|---|---|---|---|
| TASK-01 Existing Code Gap Analysis | Done / Phase1 GO | `f90561fff98dcc86ec4261b38e6c32f04c9a9f96` | _history/TASK-01_*.md |
| TASK-02 Team Core Contract Implementation & Composition | Done / Phase 1 complete | `70825632e033e64778d5373d6d8da2b619a56ad8` | _history/TASK-02_*.md |
| TASK-03 Spawn Vertical Slice | Done / Phase 2 complete | `f8c76c4611e582e99245c9638f3dc5206db3e868` | _history/TASK-03_*.md |
| TASK-04 Messaging Vertical Slice | Done / Phase 3 complete | `b007aa4be943ed6fa6ebade27b7f08a18cd94076` | _history/TASK-04_*.md |
| TASK-05 Task Collaboration | Done / Phase 4 complete | `fbed4f01d15fd0e48c30480d0104f731ec9437f9` | [Completion report](_history/TASK-05_completion.md) / [Accepted review](_history/TASK-05_completion-review.md) |
| TASK-06 Shutdown / Teardown / Failure Closure | Done / Phase 5 complete | `b17eb85400e98bf2b6cb51387dfd805bafc3a547` | [Completion report](_history/TASK-06_completion.md) / [Accepted review](_history/TASK-06_completion-review.md) |
| TASK-07 Integration / Architecture Enforcement | Done / Phase 6 complete | `78445829210a113d279b9b1f45197811aa645cd9` | [Completion report](_history/TASK-07_completion.md) / [Accepted review](_history/TASK-07_completion-review.md) |
| TASK-08 Optional Real-model E2E Smoke | Done / Optional Smoke complete | `a440cef4c56764093f8ee66b6a279529595e059e` | [Completion report](_history/TASK-08_completion.md) / [Accepted review](_history/TASK-08_completion-review.md) |
| TASK-09 Extended Real-model Runtime Acceptance | Done / Optional Live Acceptance complete | `dc958281fdd4b664c5de4696607c855cae36cb3d` | [Completion report](_history/TASK-09_completion.md) / [Accepted review](_history/TASK-09_completion-review.md) |
