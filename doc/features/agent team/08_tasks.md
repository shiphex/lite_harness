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

> 下列内容是基于当前代码的初步观察，不是本任务的预设结论。
> 执行时必须用独立证据将每项标记为 `confirmed`、`refuted` 或 `qualified`。

| ID | Preliminary code fact | Initial evidence |
| --- | --- | --- |
| CF-01 | `AgentRuntime` 已存在。 | `core/runtime.py::AgentRuntime` |
| CF-02 | 当前 MasterAgent 和 Subagent 均通过 `query_loop` 执行。 | `core/agent.py::master_agent`、`tools/subagent.py::run_subagent` |
| CF-03 | `task_system` 已使用 JSON 持久化任务。 | `tools/task_system.py::TaskStore.create`、`TaskStore.save`、`TaskStore.load` |
| CF-04 | `claim_task` / `complete_task` 已存在，但当前是绑定模块级全局 `TASKS` 的函数，尚未形成可直接注入 TeamRuntime 的实例协议。 | `tools/task_system.py::TASKS`、`claim_task`、`complete_task` |
| CF-05 | 当前目标分支中未发现 team-level member registry。 | 当前代码树与 `MemberRegistry` 符号搜索 |
| CF-06 | 当前目标分支中未发现 mailbox abstraction。 | 当前代码树与 `MailboxHandle` / `MessageBus` 符号搜索 |

## Accepted Design Constraints

| ID | Constraint | Source |
| --- | --- | --- |
| DC-01 | TeamAgent 复用现有 `AgentRuntime`，不新建一套 TeamAgentRuntime。 | `01_problem.md` §2.1、`02_architecture.md` §2.2 |
| DC-02 | TeamAgent 必须通过统一 `query_loop` 执行。 | `01_problem.md` SC-02、`07_test_plan.md` ARCH-04 |


# TASK-01 Existing Code Gap Analysis

Status:
Ready

Goal:
验证 Current Facts，并仅深入分析足以正确规划 Phase 1 的现有代码现实。以最终回复形式提交可复核的证据和 `GO/NO-GO for Phase 1` 结论。

References:

- REQUIREMENT: `01_problem.md` §2 Goal、§3 Non-goal、§4 Success Criteria
- FACTS: 本文 `Current Facts` 与 `Accepted Design Constraints`
- ARCH: `02_architecture.md`、`03_runtime.md`
- CONTRACT: `04_contracts.md`
- FAILURE: `05_failures.md`
- ADR: `06_decisions.md` 中的 ADR-001～ADR-006
- TEST: `07_test_plan.md` 与 `01_problem.md` 中的 SC-01～SC-07

Preconditions:

- `01_problem.md`～`07_test_plan.md` 是当前设计基线。
- `feature/team` 是目标分支。
- `feature/agent_teams` 只作为只读参考。

Allowed scope:

- 只读检查 Runtime、query loop、master/subagent、TaskStore、工具注册、事件和测试设施。
- 可运行不改写仓库文件的测试或静态搜索。
- 必须先完成当前代码检查；只有在存在具体 Phase 1 未决问题时，才可使用 `git show` 定向检查旧分支中的对应符号。
- 分析结果仅通过最终回复提交，不新增差距分析文档。

Must:

- 首先记录当前 HEAD、Git 工作区状态、测试命令和实际结果。测试成功或失败都必须如实报告；失败本身不使差距分析无法完成。
- 用独立代码证据验证每条 Current Fact，并标记为 `confirmed`、`refuted` 或 `qualified`。
- 对 TeamRuntime、TeamCoordinator、LifecycleManager、MemberRegistry、MessageBus、MailboxHandle、TeamAgent、TaskStore 集成和 Master 工具入口做浅层盘点；每项只记录代码证据、`reuse/adapt/new/avoid` 结论、适用契约和目标 Phase。
- 仅深入分析 Phase 1 所需的 AgentRuntime/RuntimeFactory 复用边界、TeamRuntime composition 与服务实例所有权、TaskStore 全局状态与实例注入、MemberRegistry 状态所有权，以及已接受 Contract 在当前代码结构中的可落实性。
- 将 `run_turn()` 与执行监督延后到 Spawn，mailbox capacity 延后到 Messaging，assignment 详细语义延后到 Task Collaboration，teardown failure aggregation 延后到 Shutdown，各纵切的具体 typed failure 变体延后到对应任务。
- 如果定向检查了旧分支，只记录与具体 Phase 1 问题相关的可参考模式与不可继承边界。
- 给出 `GO/NO-GO for Phase 1` 结论；只有影响 Phase 1 的未解决设计冲突可以阻塞下一阶段。

Must not:

- 不实现或复制 `team/` 代码。
- 不修改任何仓库文件，包括生产代码、测试、设计文档和本任务文档。
- 不深入研究已明确延后到后续 Phase 的问题。
- 不引入 worktree/workspace、空闲自动领任务、Scheduler、idle timeout 或成本回收。
- 不自动继承当前 Spec 未定义的旧分支机制；如果认为后续必需，只能记录为 Design Delta。
- 不通过实现细节擅自填补设计冲突。

Verify:

- 最终回复包含 Baseline、Current Facts Validation、Component Inventory、Phase 1 Blockers、Deferred Questions、Design Deltas、GO/NO-GO for Phase 1 和 Handoff 八部分。
- 所有结论都附有文件路径、符号或设计条目证据。
- 报告必须记录测试命令和实际结果，不把固定的 passed 数量作为验收条件。
- 执行前后的 Git 状态一致。
- `GO/NO-GO` 只由 Phase 1 Blockers 决定；Deferred Questions 不得阻塞 Phase 1。

Handoff:

- Codex 只提交最终报告，不修改仓库。
- Human 审阅报告，并决定接受、拒绝或要求补充证据。
- 只有被 Human 接受的事实才更新到 Current Facts，被接受的设计变化才更新到 `01_problem.md`～`07_test_plan.md`。
- Human Review 完成后，再展开下一个详细任务。

Design delta:

- 发现 Spec 缺失或矛盾时，记录来源、影响、备选方案和推荐项。
- 阻塞受影响的后续任务，等待设计决策，不通过扩大实现范围解决。
