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
| [ ] | Phase 2 | Spawn vertical slice             | Master → Coordinator → Lifecycle → Registry  | Spawn Vertical Slice |
| [ ] | Phase 3 | Messaging vertical slice         | TeamAgent → MailboxHandle → MessageBus       | Messaging Vertical Slice |
| [ ] | Phase 4 | Task collaboration               | MasterAgent + existing TaskStore + TeamAgent | Task Collaboration |
| [ ] | Phase 5 | Shutdown / teardown / failures   | 生命周期和 rollback 闭环                      | Shutdown / Teardown / Failure Closure |
| [ ] | Phase 6 | Integration / architecture enforcement | SC、ARCH、Failure tests                | Integration / Architecture Enforcement |


# Current Facts

> TASK-01 与 TASK-02 已使用独立代码证据验证下列事实，Human Review 已接受验证结果。

Validated against: `70825632e033e64778d5373d6d8da2b619a56ad8`

| ID | Status | Confirmed code fact | Evidence |
| --- | --- | --- | --- |
| CF-01 | `confirmed` | `AgentRuntime` 已存在。 | `7082563/core/runtime.py:113` |
| CF-02 | `confirmed` | 当前 MasterAgent 和 Subagent 均通过 `query_loop` 执行。 | `7082563/core/agent.py:147`、`7082563/tools/subagent.py:167` |
| CF-03 | `confirmed` | `task_system` 使用现有 `TaskStore` 与 JSON 文件持久化任务。 | `7082563/tools/task_system.py:49`、`7082563/tools/task_system.py:127`、`7082563/tools/task_system.py:201`、`7082563/tools/task_system.py:217` |
| CF-04 | `confirmed` | task operations 已支持显式 `store=` 注入，未注入时动态使用全局 `TASKS`。 | `7082563/tools/task_system.py:247`、`7082563/tools/task_system.py:253`、`7082563/tools/task_system.py:367`、`7082563/tools/task_system.py:395` |
| CF-05 | `confirmed` | `MemberRegistry` 已作为 MemberState 的 authoritative owner，通过受控 `transition()` 应用状态变化。 | `7082563/team/registry.py:65`、`7082563/team/registry.py:138` |
| CF-06 | `confirmed` | `MessageBus` 已作为 team-scoped mailbox ownership shell 存在，尚未实现 messaging behavior。 | `7082563/team/messaging.py:4` |
| CF-07 | `confirmed` | `TeamRuntime` 已独立组装并持有 MemberRegistry、MessageBus、TaskStore、LifecycleManager 与 TeamCoordinator。 | `7082563/team/runtime.py:14`、`7082563/team/runtime.py:23` |

## Accepted Design Constraints

| ID | Constraint | Source |
| --- | --- | --- |
| DC-01 | TeamAgent 复用现有 `AgentRuntime`，不新建一套 TeamAgentRuntime。 | `01_problem.md` §2.1、`02_architecture.md` §2.2 |
| DC-02 | TeamAgent 必须通过统一 `query_loop` 执行。 | `01_problem.md` SC-02、`07_test_plan.md` ARCH-04 |
| DC-03 | TeamRuntime 是独立于 AgentRuntime 的 team composition root，负责组装并持有 team-scoped shared services；具体代码落点不是架构约束。 | `02_architecture.md` §2.1、`06_decisions.md` ADR-001 |
| DC-04 | MemberRegistry 是 MemberState 的唯一 authoritative owner；所有状态变化经过受控转换入口，STOPPED / FAILED record 保留到 TeamRuntime 最终释放。 | `02_architecture.md` §2.4～2.5、`03_runtime.md` §1.2、`04_contracts.md` §2.5、`06_decisions.md` ADR-002 |
| DC-05 | 每个 TeamRuntime 使用独立的现有 TaskStore；Team 路径采用显式 store 注入，不复制任务逻辑，并保持全局 `TASKS` 工具路径兼容。 | `02_architecture.md` §2.1、`04_contracts.md` §2.2 / §3.2、`06_decisions.md` ADR-003 |
| DC-06 | 设计和测试引用现有 runtime factory 时使用实际符号 `RuntimeFactory`。 | `f90561f/core/runtime.py:143`、`07_test_plan.md` ARCH-01 |


# TASK-02 Team contract implementation / composition

Status:
Done / Phase 1 complete

Goal: 
落实 Contract、建立 TeamRuntime shared services composition（可以构造一个独立 TeamRuntime，它拥有正确的 team-scoped core services，但还没有实现 TeamAgent spawn、messaging 和 task collaboration）。

References:
- REQUIREMENT: `01_problem.md` §2.1、§3 Non-goal、§4 Success Criteria 
- FACTS: 本文 `Current Facts` 与 `Accepted Design Constraints`
- ARCH: `02_architecture.md` §1.1、§2.1、`03_runtime.md` §1.1
- CONTRACT: `04_contracts.md` §2.2、§2.5、§3.2 和 04_contracts.md §2.3、§2.4、§3.1
- FAILURE: `05_failures.md` §1
- ADR: `06_decisions.md` 中的 ADR-001～003
- TEST: `07_test_plan.md` §1、ARCH-01、ARCH-05、ARCH-06、STORE-01、STORE-02、REGISTRY-01、REGISTRY-02

Preconditions:
- `01_problem.md`～`07_test_plan.md` 是当前设计基线。
- `feature/team` 是目标分支。
- `feature/agent_teams` 只作为只读参考。

Allowed scope:
- Primary scope:
   - team/*
   - tools/* 的最小 Team integration seam
   - tests/team/* 以及为 tools/task_system compatibility 所需的最小测试
- Out-of-scope modification:
   - core/* 默认只读；
   - 若必须修改才能满足已接受 Contract，
   - 停止并报告 Design Delta。
- TASK-02 落实的是 Phase 1 所需的 structural contract / dependency boundary，不要求提前实现后续 Phase 的 behavioral contract，也不得为了“接口完整”新增无行为的占位方法。


Must:
- TeamRuntime 的 `Contract types`、`minimal service implementations / shells`、`TeamRuntime composition` 
- `MemberRegistry`: 最小的 constructor / empty state / basic contract
- `MessageBus`: 最小的能被 composition 构造
- `LifecycleManager`: 最小的依赖持有/contract
- `TeamCoordinator`: 最小 orchestration shell / dependency boundary
- `TaskStore integration`: TeamRuntime 能持有独立 existing TaskStore，建立 scoped injection seam

Must not:
- 不把 Registry/Bus/Task 等内部行为塞进 TeamRuntime/Coordinator
- TeamRuntime 独立，不修改 AgentRuntime
- 不 spawn TeamAgent，不实现 messaging behavior，不做 task assignment
- 不破坏 task_system backward compatibility
- 不修改 AgentRuntime ownership/state model
- 不引入 Scheduler/worktree
- 不复制 task_system behavior
- 不实现 `TeamCoordinator` spawn / assign / teardown use case
- 不实现 `TaskStore integration` task collaboration

| Phase 1 做 | Phase 1 不做 |
|---|---|
| TeamRuntime composition | TeamAgent spawn |
| Core service boundaries | Messaging behavior |
| Registry core state semantics | Task assignment/collaboration |
| Team-scoped TaskStore seam | Lifecycle worker behavior |
| Isolation / compatibility tests | Scheduler / worktree |
| Minimal Coordinator/Lifecycle/Bus structure | 修改 AgentRuntime ownership |

Verify:
- TeamRuntime 构造成功
- exactly one core service each
- 两个 TeamRuntime 的 mutable team state 不共享
- 不创建 AgentRuntime
- existing global task path 不回归
- Registry core invariant 成立
- scope creep：控制 Allowed scope + diff audit

Handoff:
- 动手前，Codex 只提交 Preflight Brief，不修改仓库。(Baseline、Planned changes、Target files/modules、Relevant constraints、Open blockers / Design Deltas、Ready / Blocked)
- Human 审阅报告，并决定接受、拒绝或要求补充证据。
- 只有被 Human 接受的事实才更新到 Current Facts，被接受的设计变化才更新到 `01_problem.md`～`07_test_plan.md`。
- Human Review 完成后，才能开始实现。
- Completion Report 没有经过 Human 接受前，TASK-02 仍然是 In Progress，不得标记 Done / Phase 1 complete。
- After coding 提交：Completion Report(Implemented、Files changed、Tests、Boundary checks、Design deltas、Remaining risks、Task Done / Blocked)

Design delta:
- 如果实现过程中发现当前 Spec 不成立，记录发现，
停止擅自扩张实现，按 Design Change 流程处理。


# Completed Tasks

| Task | Outcome | End commit | History |
|---|---|---|---|
| TASK-01 Existing Code Gap Analysis | Done / Phase1 GO | `f90561fff98dcc86ec4261b38e6c32f04c9a9f96` | _history/TASK-01_*.md |
| TASK-02 Team Core Contract Implementation & Composition | Done / Phase 1 complete | `70825632e033e64778d5373d6d8da2b619a56ad8` | _history/TASK-02_*.md |
