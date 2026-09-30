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

TASK-05 / Phase 4 已完成验收，证据见 [`_history/TASK-05_completion.md`](_history/TASK-05_completion.md) 与 [`_history/TASK-05_completion-review.md`](_history/TASK-05_completion-review.md)。下方 [TASK-06 任务设计](#task-06-shutdown--teardown--failure-closure)已完成[原设计审阅](_history/TASK-06_human-review.md)和[FAILED 任务恢复补充审阅](_history/TASK-06_recovery-review.md)，并形成[实现报告](_history/TASK-06_completion.md)。下一道门槛是 [`Human_Review.md`](Human_Review.md) 的 TASK-06 完成审阅；Phase 5 未勾选。

# TASK-06 Shutdown / Teardown / Failure Closure

Status:
Implementation Complete / Awaiting Completion Review

Goal:
在现有同步任务执行、成员状态和 team-scoped 消息能力之上，建立 Master 显式停止 TeamAgent、team teardown 与 fatal failure closure 的统一生命周期路径。停止或失败必须可观察，成员状态由 MemberRegistry 维护，任务事实由现有 TaskStore 维护，mailbox 由 MessageBus 维护；teardown 处理部分失败而不虚报完成。

References:
- REQUIREMENT: `01_problem.md` §2.1 Capability、§3 Non-goal、SC-04～SC-07
- FACTS: 本文 `Current Facts` 与 `Accepted Design Constraints`；TASK-05 完成验收见 [`_history/TASK-05_completion-review.md`](_history/TASK-05_completion-review.md)
- ARCH / RUNTIME: `02_architecture.md` §2.3～2.6、`03_runtime.md` §1.2～1.4 / §2
- CONTRACT / FAILURE: `04_contracts.md` §2.2～2.5 / §3.1～3.3、`05_failures.md` §1、F-STOP-01～05、F-STATE-01、F-MSG-03、F-TASK-03～04
- ADR / TEST: `06_decisions.md` ADR-013～015、`07_test_plan.md` STOP-01～10 / ARCH-02～03 及 SC-04～05 的追踪行
- PREFLIGHT: [`_history/TASK-06_preflight.md`](_history/TASK-06_preflight.md)；已接受设计归档于 [`_history/TASK-06_human-review.md`](_history/TASK-06_human-review.md)，当前完成审阅入口为 [`Human_Review.md`](Human_Review.md)

Preconditions:
- TASK-05 / Phase 4 已完成审阅；Master 可显式分配任务，TeamCoordinator 同步运行一次 `TeamAgent.run(prompt)`，普通执行异常保留原 owner 的续跑路径。
- 生命周期停止、teardown 与 fatal 主路径已实现；FAILED 成员持有任务的恢复补充设计见 [`_history/TASK-06_recovery-review.md`](_history/TASK-06_recovery-review.md)，完成验收仍待审阅。

Allowed scope:
- 设计接受后，在 `team/*` 建立 Coordinator → LifecycleManager 的停止、fatal 报告、teardown 与最终释放路径，以及 Registry / MessageBus / TaskStore 所需的最小受控协作接口。
- 在 `tools/team.py` 中增加 Master 专属生命周期工具；仅为 Master session 收尾所需的最小连接允许修改 `core/agent.py`，不得改变统一 `AgentRuntime` / `query_loop` 的通用执行语义。
- 增加 `tests/team/*` 与必要的 session / tool 边界测试；保持既有工具与任务行为兼容，完成后提交独立报告供完成审阅。

Must:
- 所有 TeamAgent 停止和 teardown 请求经过统一生命周期入口；MemberState 仅由 MemberRegistry 的受控 transition 改变，STOPPED / FAILED record 保留到 TeamRuntime 最终释放。
- 保留已接受的 TASK-05 任务事实与恢复语义：普通执行异常、未完成任务和已完成但成员收尾失败必须呈现实际 task/member 状态，不得伪报完成或静默重置 owner。
- shutdown / teardown 具有可观察、可重试的结果；teardown best-effort 处理每个成员并汇总失败，fatal runtime failure 有可查询的终态。
- MessageBus 继续拥有 mailbox storage；成员终态后的消息行为与并发停止顺序按设计裁决定义，并以确定性测试证明。
- 落实已接受的 DD-01～DD-06：活动 turn 与原 owner 未完成/待修复任务拒绝停止；正常 `q/exit` 拒绝在部分失败后结束会话；fatal、最终释放和消息顺序遵循 ADR-013 / ADR-014。
- 按 CR-02 / ADR-015 让 Master 对 FAILED owner 的 `in_progress` 任务逐项创建全新 TeamAgent，原子记录 owner 交接并同步执行；交接失败保留明确且可恢复的任务归属，不动用现有 IDLE 成员。

Must not:
- 不把尚未实现的 Phase 5 行为、新增测试或成功标准标为已完成。
- 不引入后台 worker、强制中断能力、Scheduler、自动扫描或自动任务重分配、消息驱动执行、持久消息、跨进程事务、worktree、idle timeout 或 token/cost eviction。Master 的逐项显式 FAILED 任务恢复按 ADR-015 执行。
- 不绕过 Registry、TaskStore 或 MessageBus 直接修改成员、任务或 mailbox；不把正常 shutdown 当作 `unregister`，也不在失败未清理时提前宣称 team 已释放。
- 不要求删除 RuntimeFactory 生成的 diagnostic artifacts，也不把可选真实模型 smoke 作为 Phase 5 的完成条件。

Design review accepted:
- [`_history/TASK-06_preflight.md`](_history/TASK-06_preflight.md) 保留原预检提案；用户的实际裁决归档于 [`_history/TASK-06_human-review.md`](_history/TASK-06_human-review.md)，并已传播至 02～07。下列条目是已接受设计，不代表已实现。

| ID | 已接受裁决 |
| --- | --- |
| DD-01 | Master 专属停止/teardown 入口，LifecycleManager 持有 wrapper；正常退出尝试 teardown 并呈现失败。 |
| DD-02 | 活动 turn、未完成任务或待恢复收尾拒绝停止；可运行的原 owner 显式续跑，FAILED owner 的任务按 ADR-015 恢复后重试。正常 `q/exit` 遇失败拒绝退出。 |
| DD-03 | 普通执行异常可续跑；明确 fatal 才转 FAILED 并保留错误与任务事实。 |
| DD-04 | Teardown best-effort 汇总；失败保留 team 供重试，全部安全停止后最终释放。 |
| DD-05 | 消息与 shutdown/fatal transition 共用顺序边界，终态后拒绝收发。 |
| DD-06 | 无后台 worker 强制关闭；活动同步 turn 返回可观察忙碌错误。 |

- 用户在完成审阅期间接受补充设计 CR-02：Master 逐项创建全新 TeamAgent 恢复 FAILED 成员的未完成任务，现有 IDLE 成员不接手；归档见 [`_history/TASK-06_recovery-review.md`](_history/TASK-06_recovery-review.md) 与 ADR-015。CR-01 的原实现已获同意；CR-03 仍是完成审阅后的状态勾选门槛。

- 完成审阅接受前，Phase 5、SC-04～SC-07 和新增检查项保持未完成；不得以既有 Registry 单元测试或预检回归结果替代 TASK-06 验收。

Verify after acceptance and implementation:
- 使用 fake runtime / fake loop 验证 Master 生命周期工具 → Coordinator → LifecycleManager → Registry 的完整路径，以及 IDLE、BUSY、WAITING、STOPPED、FAILED 的停止、重复停止与查询结果。
- 覆盖活动同步执行、未完成任务、普通执行异常与 fatal 的区别；验证 TaskStore 中的 owner/status 和 Registry 中的成员状态不会被静默重置。
- 注入逐成员停止和 teardown 清理失败，验证 best-effort 汇总、重试、最终释放边界及终态 record 的保留；并发 send/receive 与 shutdown/fatal 的行为按已接受裁决验证。
- 验证 FAILED 任务的新成员恢复、旧任务文件兼容、交接记录持久化、重复/并发请求、spawn/写入/状态转换失败及再次 fatal；确保现有 IDLE 成员上下文不受影响。
- 保持所有 `07_test_plan.md` 已勾选回归项通过，运行针对性与全量自动测试、compileall、`git diff --check`，并审查 diff 未引入 Non-goal 或 Phase 6 / 可选 smoke 能力。

Handoff:
- 设计审阅已按用户实际裁决归档并传播到 02～07、ADR、测试追踪及本文；已接受范围的实现与验证记录见 TASK-06 Completion Report。
- [Completion Report](_history/TASK-06_completion.md) 已形成；其独立完成人工审阅接受前，TASK-06 保持进行中，Phase 5 与新测试不勾选；有证据的验收完成后才更新 Completed Tasks 和结束提交引用。

# Completed Tasks

| Task | Outcome | End commit | History |
|---|---|---|---|
| TASK-01 Existing Code Gap Analysis | Done / Phase1 GO | `f90561fff98dcc86ec4261b38e6c32f04c9a9f96` | _history/TASK-01_*.md |
| TASK-02 Team Core Contract Implementation & Composition | Done / Phase 1 complete | `70825632e033e64778d5373d6d8da2b619a56ad8` | _history/TASK-02_*.md |
| TASK-03 Spawn Vertical Slice | Done / Phase 2 complete | `f8c76c4611e582e99245c9638f3dc5206db3e868` | _history/TASK-03_*.md |
| TASK-04 Messaging Vertical Slice | Done / Phase 3 complete | `b007aa4be943ed6fa6ebade27b7f08a18cd94076` | _history/TASK-04_*.md |
| TASK-05 Task Collaboration | Done / Phase 4 complete | `fbed4f01d15fd0e48c30480d0104f731ec9437f9` | [Completion report](_history/TASK-05_completion.md) / [Accepted review](_history/TASK-05_completion-review.md) |
