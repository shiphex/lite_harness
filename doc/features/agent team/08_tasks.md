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
| DC-07 | Spawn 只发布被动 TeamAgent wrapper；IDLE 是 commit，spawn 本身不启动线程或模型执行。 | `06_decisions.md` ADR-007 |
| DC-08 | 一个 Master session 对应一个 sibling TeamRuntime；composition scope 显式共享 session_id，并通过 Master-only bound handler 连接两者。 | `06_decisions.md` ADR-008 |
| DC-09 | TeamAgent 有独立 runtime/state/history/identity，Phase 2 使用已接受的 provisional read-only execution policy。 | `06_decisions.md` ADR-009 |
| DC-10 | 只有 LifecycleManager 创建并逻辑持有 TeamAgent runtime/wrapper；commit 前逆序 rollback，不承诺删除 runtime diagnostic artifacts。 | `06_decisions.md` ADR-010 |


# TASK-03 Spawn Vertical Slice

Status:
In Progress / Awaiting Human Review

Goal:
打通 Master team tool → TeamCoordinator → LifecycleManager → RuntimeFactory / AgentRuntime → MemberRegistry 的完整 spawn 垂直链路。MasterAgent 可以创建至少一个 TeamAgent；成功创建的 TeamAgent 复用现有 AgentRuntime，并通过统一 `query_loop` 执行。

References:
- REQUIREMENT: `01_problem.md` §2.1、§3 Non-goal、SC-01、SC-02、SC-04、SC-06、SC-07
- FACTS: 本文 `Current Facts` 与 `Accepted Design Constraints`
- ARCH: `02_architecture.md` §1.1、§2.1～§2.6
- RUNTIME: `03_runtime.md` §1.1～§1.2
- CONTRACT: `04_contracts.md` §2.4、§2.5、§3.1～§3.2
- FAILURE: `05_failures.md` §1、F-SPAWN-01、F-SPAWN-02、F-STATE-01
- ADR: `06_decisions.md` 中的 ADR-001、ADR-002、ADR-007～ADR-010
- TEST: `07_test_plan.md` §1、STATE-01、F-SPAWN-01、F-SPAWN-02、ARCH-03、ARCH-04，以及所有已勾选的 Phase 1 回归项

Preconditions:
- `01_problem.md`～`07_test_plan.md` 是当前设计基线。
- `feature/team` 是目标分支。
- `feature/agent_teams` 只作为只读参考，不照搬其 worker、profile、worktree、messaging 或 task collaboration 设计。
- TASK-02 已完成并通过 Human Review；本文 Current Facts 以 `7082563` 的已接受代码证据为准。

Allowed scope:
- Primary scope:
   - `team/*` 中完成 spawn orchestration、lifecycle 和最小 TeamAgent execution boundary
   - `tools/*` 中 Master 可调用的最小 team spawn tool / handler seam
   - Master 与 TeamRuntime 建立连接所必需的最小 composition seam
   - `tests/team/*` 及验证 Master tool integration 所需的最小测试
- `core/*` 仅允许为 Master composition seam 做最小修改；不得改变 AgentRuntime ownership/state model、`query_loop` 通用执行语义或现有 Master/Subagent 行为。
- TASK-03 只落实 Phase 2 的 spawn vertical slice，不提前实现 Phase 3～5 的 messaging、task collaboration、shutdown 或 teardown 行为。

Must:
- 提供 MasterAgent 可调用的 spawn tool 入口，并将请求转交 `TeamCoordinator.spawn_teammate(...)`。
- TeamCoordinator 只编排 spawn use case，不直接构造 runtime、不调用 LLM、不保存 LifecycleManager 应持有的 worker 内部状态。
- 只有 `LifecycleManager.spawn(...)` 可以调用 RuntimeFactory 创建 TeamAgent 使用的现有 AgentRuntime，并协调 runtime、worker 与 registry 的创建/发布顺序。
- 使用 RuntimeFactory 生成的实际 `agent_id` 和 `agent_name` 注册 MemberRegistry；注册产生 STARTING record，spawn 成功后由 LifecycleManager 请求 `SPAWN_SUCCESS` transition，最终返回可查询的 IDLE member。
- TeamAgent 复用现有 AgentRuntime / `query_loop`，保持独立运行状态与 history；不得创建 TeamAgentRuntime 或第二套 agent loop。
- runtime 创建、member 注册、worker 创建/启动或发布任一步骤失败时，清理此前产生的部分资源；发布成功前已注册的 STARTING record 使用 `SPAWN_ROLLBACK` 移除，最终不得残留 member 或 worker。
- domain failure 使用 typed error/result，不允许 silent failure；自动测试使用 fake runtime / fake loop，不调用真实模型。

Must not:
- 不实现 MessageBus / MailboxHandle 的 send、receive 或 mailbox storage behavior。
- 不实现 task assignment、task claim/complete binding 或 TeamAgent 自主取任务。
- 不实现 shutdown、teardown、fatal runtime supervision 等 Phase 5 行为；只实现 spawn 失败所必需的局部 rollback。
- 不引入 Scheduler、worktree、writer/researcher profile、session conversation policy 或 real-model E2E。
- 不复制 `tools/subagent.py` 的独立运行时构造逻辑，不修改 AgentRuntime 的状态所有权，也不让 TeamAgent 自行创建 AgentRuntime。
- 不把 Registry、Lifecycle 或 worker 内部行为塞进 TeamRuntime / TeamCoordinator。

| Phase 2 做 | Phase 2 不做 |
|---|---|
| Master spawn tool → Coordinator | Messaging / MailboxHandle behavior |
| LifecycleManager 创建 AgentRuntime / worker | Task assignment / collaboration |
| Registry STARTING → IDLE 发布 | Shutdown / teardown / fatal supervision |
| TeamAgent 复用 query_loop | Scheduler / worktree / profiles |
| Spawn failure rollback | Real-model E2E |

Preflight resolution (Accepted):
- DD-01～DD-04 已完成人审并接受；完整裁决见 [`_history/TASK-03_human-review.md`](_history/TASK-03_human-review.md)。
- Master session composition scope 创建 sibling Master AgentRuntime / TeamRuntime，并以 per-instance bound handler 连接。
- TeamAgent 是 LifecycleManager 逻辑持有的被动 execution wrapper；`run(prompt)` 复用既有 `query_loop`。
- `TeamCoordinator.spawn_teammate(...)` 与 `LifecycleManager.spawn(...)` 返回 MemberRecord，domain failure 使用 `SpawnError(TeamError)`。
- IDLE 是 commit；commit 前逆序清理 ownership，并以 `SPAWN_ROLLBACK` 移除 STARTING record。rollback 不删除 RuntimeFactory diagnostic artifacts。

Verify:
- happy path 必须经过 Master tool、TeamCoordinator、LifecycleManager、RuntimeFactory / AgentRuntime 与 MemberRegistry，返回的 member state 为 IDLE。
- spawn_teammate 只进入 MasterAgent 的 allowed tool set / handler binding；TeamAgent 与普通 Subagent 不暴露该能力。
- Registry record 的 `agent_id` / `agent_name` 与 RuntimeFactory 返回的 AgentRuntime 一致。
- TeamAgent 执行进入现有 `query_loop`；不存在 TeamAgentRuntime 或第二套 loop。
- F-SPAWN-01：runtime create 失败后无 member、无 leaked worker。
- F-SPAWN-02：register 或发布失败后 runtime / worker 被清理，STARTING record 被 rollback，最终无 member。
- ARCH-03：Agent creation 入口必须经过 LifecycleManager。
- ARCH-04：全部 TeamAgent 使用现有 AgentRuntime / `query_loop`。
- 所有 `07_test_plan.md` 已勾选项目持续通过；使用 fake runtime / fake loop，不执行 real-model E2E。
- scope creep：控制 Allowed scope，并通过 diff audit 确认未提前实现 Phase 3～5 或 Non-goal。
- Optional manual smoke：在本地模型/API配置可用时，可运行 uv run main.py 手工验证 MasterAgent 能通过 team tool 触发 spawn；该项不作为 TASK-03 Done / Phase 2 gate。

Handoff:
- 动手前，Codex 只提交 Preflight Brief，不修改仓库。(Baseline、Planned changes、Target files/modules、Relevant constraints、Open blockers / Design Deltas、Ready / Blocked)
- Human 审阅报告，并决定接受、拒绝或要求补充证据。
- 只有被 Human 接受的事实才更新到 Current Facts，被接受的设计变化才更新到 `01_problem.md`～`07_test_plan.md`。
- Human Review 完成后，才能开始实现。
- Completion Report 没有经过 Human 接受前，TASK-03 仍然是 In Progress，不得勾选 Phase 2 或标记 Done / Phase 2 complete。
- After coding 提交：Completion Report(Implemented、Files changed、Tests、Boundary checks、Design deltas、Remaining risks、Task Done / Blocked)

Design delta:
- Preflight DD-01～DD-04 已接受并传播至 `02_architecture.md`～`08_tasks.md`；实现阶段未发现新的 Design Delta。


# Completed Tasks

| Task | Outcome | End commit | History |
|---|---|---|---|
| TASK-01 Existing Code Gap Analysis | Done / Phase1 GO | `f90561fff98dcc86ec4261b38e6c32f04c9a9f96` | _history/TASK-01_*.md |
| TASK-02 Team Core Contract Implementation & Composition | Done / Phase 1 complete | `70825632e033e64778d5373d6d8da2b619a56ad8` | _history/TASK-02_*.md |
