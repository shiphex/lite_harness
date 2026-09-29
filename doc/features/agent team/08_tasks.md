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
| [ ] | Phase 3 | Messaging vertical slice         | TeamAgent → MailboxHandle → MessageBus       | Messaging Vertical Slice |
| [ ] | Phase 4 | Task collaboration               | MasterAgent + existing TaskStore + TeamAgent | Task Collaboration |
| [ ] | Phase 5 | Shutdown / teardown / failures   | 生命周期和 rollback 闭环                      | Shutdown / Teardown / Failure Closure |
| [ ] | Phase 6 | Integration / architecture enforcement | SC、ARCH、Failure tests                | Integration / Architecture Enforcement |


# Current Facts

维护规则：切换当前任务时，只保留与该任务有关、且有验收证据的代码事实，目标约 7～8 条。

> TASK-01～TASK-03 的下列代码事实已通过对应审阅；TASK-03 的受托完成审阅见 [`_history/TASK-03_completion-review.md`](_history/TASK-03_completion-review.md)。

Validated against: CF-01～CF-03 为 `70825632e033e64778d5373d6d8da2b619a56ad8`；CF-04～CF-07 为 `04224aeffcd1579e214a2a8bb90969225bf1878c`。

| ID | Status | Confirmed code fact | Evidence |
| --- | --- | --- | --- |
| CF-01 | `confirmed` | `MemberRegistry` 已作为 MemberState 的 authoritative owner，通过受控 `transition()` 应用状态变化。 | `7082563/team/registry.py:65`、`7082563/team/registry.py:138` |
| CF-02 | `confirmed` | `MessageBus` 已作为 team-scoped mailbox ownership shell 存在，尚未实现 messaging behavior。 | `7082563/team/messaging.py:4` |
| CF-03 | `confirmed` | `TeamRuntime` 已独立组装并持有 MemberRegistry、MessageBus、TaskStore、LifecycleManager 与 TeamCoordinator。 | `7082563/team/runtime.py:14`、`7082563/team/runtime.py:23` |
| CF-04 | `confirmed` | Master session 建立 sibling TeamRuntime，并仅向 Master 实例绑定 `spawn_teammate` 工具。 | `04224ae/core/agent.py:124`、`04224ae/core/agent.py:125`、`04224ae/core/agent.py:136`、`04224ae/tools/team.py:11` |
| CF-05 | `confirmed` | `LifecycleManager.spawn()` 创建 TeamAgent 的 AgentRuntime、发布 IDLE member，并在 commit 前失败时清理逻辑 ownership 与 STARTING record。 | `04224ae/team/lifecycle.py:60`、`04224ae/team/lifecycle.py:81`、`04224ae/team/lifecycle.py:90`、`04224ae/team/lifecycle.py:161`、`04224ae/team/lifecycle.py:167` |
| CF-06 | `confirmed` | 被动 TeamAgent wrapper 的 `run(prompt)` 进入现有 `query_loop`；spawn 本身不启动执行。 | `04224ae/team/agent.py:27`、`04224ae/team/agent.py:33`、`04224ae/team/lifecycle.py:77` |
| CF-07 | `confirmed` | Phase 2 的 TeamAgent 仅配置 `read_file`、`glob`、`load_skill` 三个只读工具，尚未暴露消息能力。 | `04224ae/team/lifecycle.py:26`、`04224ae/team/lifecycle.py:121` |

## Accepted Design Constraints

维护规则：只摘要约 7～8 条跨阶段约束；除重大方向或理念变更外，不随普通任务进度改写。

| ID | Constraint | Source |
| --- | --- | --- |
| DC-01 | TeamAgent 复用现有 `AgentRuntime` 与统一 `query_loop`，不新建 TeamAgentRuntime 或第二套 loop。 | `01_problem.md` §2.1 / SC-02、`02_architecture.md` §2.2、`07_test_plan.md` ARCH-04 |
| DC-02 | TeamRuntime 独立于 AgentRuntime，组装并持有 team-scoped shared services；一个 Master session 对应一个 sibling TeamRuntime，共享显式 session_id，并通过 Master-only bound handler 连接。具体代码落点不是架构约束。 | `02_architecture.md` §2.1、`06_decisions.md` ADR-001 / ADR-008 |
| DC-03 | MemberRegistry 是 MemberState 的唯一 authoritative owner；所有状态变化经过受控转换入口，STOPPED / FAILED record 保留到 TeamRuntime 最终释放。 | `02_architecture.md` §2.4～2.5、`03_runtime.md` §1.2、`04_contracts.md` §2.5、`06_decisions.md` ADR-002 |
| DC-04 | 每个 TeamRuntime 使用独立的现有 TaskStore；Team 路径采用显式 store 注入，不复制任务逻辑，并保持全局 `TASKS` 工具路径兼容。 | `02_architecture.md` §2.1、`04_contracts.md` §2.2 / §3.2、`06_decisions.md` ADR-003 |
| DC-05 | MessageBus 管理 team-scoped mailbox storage；Agent 只通过自身的 MailboxHandle 使用收发能力，不直接持有或修改 mailbox。 | `02_architecture.md` §2.3、`04_contracts.md` §2.1 / §2.3、`06_decisions.md` ADR-004 |
| DC-06 | 消息执行语义采用 one-message-one-turn；本阶段只落实收发边界，不据此启动 TeamAgent 执行。 | `06_decisions.md` ADR-006、`03_runtime.md` §1.1 / §1.4 |
| DC-07 | Spawn 只发布被动 TeamAgent wrapper，IDLE 是 commit；只有 LifecycleManager 通过实际符号 `RuntimeFactory` 创建并逻辑持有 TeamAgent runtime/wrapper，commit 前逆序 rollback，不承诺删除 runtime diagnostic artifacts。 | `06_decisions.md` ADR-007 / ADR-010、`f90561f/core/runtime.py:143`、`07_test_plan.md` ARCH-01 |
| DC-08 | TeamAgent 有独立 runtime/state/history/identity；Phase 2 的只读 execution policy 是 provisional mechanism。 | `06_decisions.md` ADR-009 |


# TASK-04 Messaging Vertical Slice

Status:
In Progress / Awaiting Completion Review

Goal:
建立 TeamAgent → MailboxHandle → TeamRuntime-owned MessageBus → 目标 MailboxHandle 的可测试消息收发链路。Phase 3 交付明确的通信边界、路由与失败语义；收到消息不自动触发 `TeamAgent.run()` 或 `query_loop`。

References:
- REQUIREMENT: `01_problem.md` §2.1 Capability、§3 Non-goal、SC-03、SC-05～SC-07
- FACTS: 本文 `Current Facts` 与 `Accepted Design Constraints`；TASK-03 完成验收见 [`_history/TASK-03_completion-review.md`](_history/TASK-03_completion-review.md)
- ARCH: `02_architecture.md` §1.1、§2.2～§2.3、§2.6
- RUNTIME: `03_runtime.md` §1.1、§1.4
- CONTRACT: `04_contracts.md` §2.1、§2.3、§3.2
- FAILURE: `05_failures.md` §1、F-MSG-01、F-MSG-02、§3 message to STOPPED member
- ADR: `06_decisions.md` ADR-001、ADR-004、ADR-006～ADR-009、ADR-011
- TEST: `07_test_plan.md` §1、F-MSG-01～04、ARCH-02、MSG-01～03、MSG-TOOL-01，以及所有已勾选的回归项

Preconditions:
- `01_problem.md`～`07_test_plan.md` 是当前设计基线；TASK-03 已完成并通过受托完成审阅，Phase 2 的被动 spawn 与 TeamAgent execution boundary 可作为 Phase 3 起点。
- `feature/team` 是目标分支；`feature/agent_teams` 只作为只读参考，不照搬其 messaging、worker 或 task collaboration 设计。
- 进入 TASK-04 前，MessageBus 仅有 team-scoped ownership shell，没有 MailboxHandle 或 send/receive 行为；实现基线为 `f8c76c4`。

Allowed scope:
- 在 `team/*` 中实现 MailboxHandle、MessageBus 路由与 mailbox ownership，并完成 TeamRuntime、LifecycleManager、TeamAgent 之间必要的最小绑定。
- 只在消息能力确有需要且经 preflight 裁决后，增加最小的 TeamAgent 工具或 handler 接缝；不得扩展通用 Master/Subagent 工具集合。
- 增加 `tests/team/*` 及必要的工具边界测试；保留全部已接受阶段的回归测试。

Must:
- TeamAgent 通过自身的 MailboxHandle 发送和接收消息；MessageBus 负责 team-scoped mailbox storage、目标路由与入队，Agent 不直接访问其他 Agent 或 mailbox 内部存储。
- 正常收发可验证消息到达指定目标，且不同 TeamRuntime 的 mailbox 与消息互不污染。
- 目标不存在时按 F-MSG-01 拒绝；mailbox 满时按 F-MSG-02 拒绝或施加明确背压，不得静默丢失消息。已 STOPPED 的目标必须有明确、可测试的处理结果。
- domain failure 使用 typed error/result；消息操作不绕过 MemberRegistry 修改 MemberState，也不改变现有 spawn ownership 与执行边界。
- 自动测试使用确定性的 fake / in-memory 依赖，不调用真实模型；所有已勾选回归项持续通过。

Must not:
- 不因 send、receive 或消息入队自动触发 `TeamAgent.run()`、`query_loop`、后台线程或 MemberState 的 BUSY / WAITING transition；ADR-006 的 one-message-one-turn 执行语义留待执行触发阶段落实。
- 不实现 task assignment、claim/complete binding、TeamAgent 自主取任务、shutdown、teardown 或 fatal runtime supervision。
- 不引入 Scheduler、worktree、profile、conversation session policy 或 real-model E2E；不把 mailbox storage 放进 TeamAgent、TeamCoordinator 或 AgentRuntime。

Preflight resolution (Accepted):
- DD-01～DD-04 已由用户委托技术审阅接受；完整裁决见 [`Human_Review.md`](Human_Review.md)，已传播到 `02_architecture.md`～`07_test_plan.md`。
- 使用绑定实际 sender_id 的 MailboxHandle、不可变 TeamMessage、容量默认 100 条的内存 FIFO；content 上限为 16,384 字符，满载立即拒绝。
- MessageBus 只查询本 TeamRuntime Registry，STARTING / STOPPED / FAILED 成员不可收发；bus 锁不承诺与未来 shutdown 跨模块线性化。
- TeamAgent 专属消息工具通过 `ToolContext.runtime` 查找并验证 wrapper 的 handle；消息本身不启动执行。

Implementation evidence:
- [`_history/TASK-04_completion.md`](_history/TASK-04_completion.md) 记录本轮实现、自动验证与剩余风险；完成审阅接受前保持当前 In Progress 状态。

Verify:
- 两个已发布的 TeamAgent 经各自 MailboxHandle 完成发送与接收；消息只进入指定目标的 team-scoped mailbox，不暴露其他 Agent 或 MessageBus 内部存储。
- F-MSG-01、F-MSG-02、STOPPED 目标与跨 TeamRuntime 隔离均有自动测试；失败可观察且没有 silent loss。
- ARCH-02 验证 Agent communication 只能经 MailboxHandle / MessageBus；已勾选的 spawn、registry、runtime 和 task-store 回归项继续通过。
- diff audit 确认没有消息驱动执行、任务协作、shutdown / teardown 或 Non-goal 能力；不要求真实模型 smoke。

Handoff:
- 实现前提交只读 Preflight Brief，列出 baseline、拟修改模块、已验证事实、待裁决设计问题和 Ready / Blocked 结论；不在 preflight 阶段修改代码。
- Human 审阅并接受设计裁决后，才开始实现；只有被接受的新事实或设计变化才能传播到本文及对应的 `01_problem.md`～`07_test_plan.md`。
- 实现后提交 Completion Report，记录改动、测试、边界检查、设计变化与剩余风险；完成审阅接受前，TASK-04 保持 In Progress，Phase 3 与 SC-03 不勾选。


# Completed Tasks

| Task | Outcome | End commit | History |
|---|---|---|---|
| TASK-01 Existing Code Gap Analysis | Done / Phase1 GO | `f90561fff98dcc86ec4261b38e6c32f04c9a9f96` | _history/TASK-01_*.md |
| TASK-02 Team Core Contract Implementation & Composition | Done / Phase 1 complete | `70825632e033e64778d5373d6d8da2b619a56ad8` | _history/TASK-02_*.md |
| TASK-03 Spawn Vertical Slice | Done / Phase 2 complete | `f8c76c4611e582e99245c9638f3dc5206db3e868` | _history/TASK-03_*.md |
