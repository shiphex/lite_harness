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
| [√] | Phase 5 | Shutdown / teardown / failures   | 生命周期和 rollback 闭环                      | Shutdown / Teardown / Failure Closure |
| [ ] | Phase 6 | Integration / architecture enforcement | SC、ARCH、Failure tests                | Integration / Architecture Enforcement |


# Current Facts

维护规则：切换当前任务时，只保留与该任务有关、且有验收证据的代码事实，目标约 7～8 条。

> 下列事实均已在 TASK-01～TASK-06 的对应审阅中接受，并于 TASK-07 预检时对照当前代码复核；历史验收见 [`_history/`](./_history/README.md)。

Validated against: `eb9ed3b43388855f82226a525c2d324799d84883` (`feature/team`)，预检时工作区干净；全量 pytest 为 336 passed。证据细节见 [`_history/TASK-07_preflight.md`](_history/TASK-07_preflight.md)。

| ID | Status | Confirmed code fact | Evidence |
| --- | --- | --- | --- |
| CF-01 | `confirmed` | TeamRuntime 组装并持有 Registry、MessageBus、独立 TaskStore、LifecycleManager 与 Coordinator。 | `eb9ed3b/team/runtime.py:27`～`:42` |
| CF-02 | `confirmed` | Master session 创建 sibling TeamRuntime，共享显式 session_id，并将团队工具绑定在 Master 实例。 | `eb9ed3b/core/agent.py:124`～`:137`、`eb9ed3b/tools/team.py:110` |
| CF-03 | `confirmed` | LifecycleManager 是 TeamAgent runtime 的创建入口，持有已发布 wrapper，并按实际 runtime ID 绑定 mailbox handle。 | `eb9ed3b/team/lifecycle.py:87`～`:135`、`:344` |
| CF-04 | `confirmed` | TeamAgent 的 `run(prompt)` 进入既有 `query_loop`；消息工具使用实际 runtime 身份取得绑定 handle。 | `eb9ed3b/team/agent.py:30`～`:58`、`eb9ed3b/team/messaging_tools.py:39`～`:70` |
| CF-05 | `confirmed` | MessageBus 管理同步收发；停止与 fatal 状态转换使用其共同顺序边界。 | `eb9ed3b/team/messaging.py:81`～`:92`、`eb9ed3b/team/lifecycle.py:185`～`:226` |
| CF-06 | `confirmed` | Team 路径复用显式注入的 TaskStore；未注入 store 的旧路径仍使用全局 `TASKS`。 | `eb9ed3b/team/coordinator.py:73`～`:82`、`eb9ed3b/tools/task_system.py:296`～`:303` |
| CF-07 | `confirmed` | Coordinator 编排分配、原 owner 续跑及 FAILED 任务显式恢复；任务交接由现有 task_system 保存。 | `eb9ed3b/team/coordinator.py:84`～`:109`、`:138`～`:184`、`eb9ed3b/tools/task_system.py:458` |
| CF-08 | `confirmed` | LifecycleManager 处理安全停止、fatal 与可重试 teardown；最终释放前保留成员和任务事实。 | `eb9ed3b/team/lifecycle.py:156`～`:282` |

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

TASK-07 的 DD-01～DD-03 已由用户在本轮接受，设计审阅见 [`_history/TASK-07_human-review.md`](_history/TASK-07_human-review.md)。实施与验证证据见 [`_history/TASK-07_completion.md`](_history/TASK-07_completion.md)；下一道门槛是完成审阅。Phase 6 和新增检查项仍为 `[ ]`。

# TASK-07 Integration / Architecture Enforcement

Status:
Implementation Verified / Awaiting Completion Review（已实施并验证，待完成审阅）

Goal:
以同一 TeamRuntime 的全链路成功与 fatal 恢复场景，验证已接受的创建、消息、任务和生命周期契约能够组合运行；补强架构边界守卫，并补齐 SC-06/07 的 Phase 6 追踪。任务只增强验证证据，不新增运行时能力。

References:
- REQUIREMENT: `01_problem.md` §2 Goal、§3 Non-goal、SC-01～SC-07
- FACTS: 本文 `Current Facts` 与 `Accepted Design Constraints`；TASK-06 完成验收见 [`_history/TASK-06_completion-review.md`](_history/TASK-06_completion-review.md)
- ARCH / RUNTIME: `02_architecture.md` §2.1～2.6、`03_runtime.md` §1.1～1.4
- CONTRACT / FAILURE: `04_contracts.md` §2.1～3.3、`05_failures.md` F-SPAWN、F-MSG、F-STATE、F-TASK、F-STOP 各类失败路径
- ADR / TEST: `06_decisions.md` ADR-001～015；`07_test_plan.md` ARCH-01～08、INTEG-01/02 与 SC-06/07 的 Phase 6 增量追踪行
- TASK EVIDENCE: [预检报告](_history/TASK-07_preflight.md)、[已接受设计审阅](_history/TASK-07_human-review.md)、[完成报告](_history/TASK-07_completion.md)；当前完成审阅入口为 [`Human_Review.md`](Human_Review.md)

Preconditions:
- TASK-01～TASK-06 / Phase 0～5 已通过完成审阅；TASK-07 预检基线为 `eb9ed3b` 的干净工作区和 336 passed，不能将其视为 Phase 6 的全链路证据。
- DD-01～DD-03 已获用户接受并传播到 `07_test_plan.md`；新增检查项、SC-06/07 的增量追踪行与 Phase 6 仍为 `[ ]`。

Allowed scope:
- 在 `tests/team/` 增加使用实际 TeamRuntime、RuntimeFactory、工具执行器与 TaskStore、以确定性 fake loop 代替模型的成功及 fatal 恢复全链路测试。
- 在现有架构测试中以针对性的 AST import/call 检查补强 Registry、创建入口、统一 loop、Bus 访问与 Non-goal 守卫；保留运行时身份、状态所有权、隔离和兼容测试。
- 在 `07_test_plan.md` 增加 Phase 6 检查项和 SC-06/07 追踪行，并在本任务报告和审阅中记录实际证据；若发现需改变产品行为的新取舍，先补设计审阅。

Must:
- INTEG-01 串接 Master bound spawn、至少两个 TeamAgent 的专属消息收发、任务创建/分配/完成与安全 teardown；核对 session、独立身份、owner、消息边界和最终释放。
- INTEG-02 串接 `in_progress` 任务 owner 显式 fatal、首次 teardown 部分失败、Master 创建新成员恢复交接并完成任务、最终释放；核对旧 FAILED record、任务事实及交接记录。
- ARCH-07/08 针对已接受的 import/call 和模块责任设置 AST 守卫，并以受控源码片段证明导入、别名、直接访问和 Agent 侧自主领取的回退可被识别；运行时测试继续验证语义边界。
- 将 SC-06/07 的 Phase 6 增量验收与新旧测试 ID 关联；已勾选的前序检查项继续作为回归条件。

Must not:
- 不以预检基线或仅通过的垂直切片测试替代 Phase 6 全链路证据；完成审阅接受前不勾选新增项、增量追踪行或 Phase 6。
- 不新增公开 API、第二套 AgentRuntime / query loop、Scheduler、worktree、TeamAgent 自主领取、消息驱动执行或 idle/token-cost 自动淘汰；真实模型 E2E smoke 仍为 Phase 6 后可选项目。
- 不绕过 Registry、TaskStore 或 MessageBus 的状态所有权，也不因测试补强改写已接受的 01～06 设计和既有检查项。

Design review accepted:
- 用户已接受 [TASK-07 设计审阅](_history/TASK-07_human-review.md)中的 DD-01～DD-03；下列裁决确定验证范围，不等于完成验收。

| ID | 已接受裁决 |
| --- | --- |
| DD-01 | 用 fake loop 验证创建、通信、任务完成与释放的成功链路，以及 fatal 后恢复和部分 teardown 失败链路。 |
| DD-02 | 使用针对性的 AST 导入与调用守卫补强架构检查，保留运行时边界断言。 |
| DD-03 | 补齐 `07_test_plan.md` 中 SC-06/07 的 Phase 6 增量追踪行，完成审阅前保持未勾选。 |

Verification evidence pending completion acceptance:
- [完成报告](_history/TASK-07_completion.md)记录两条全链路测试、AST 守卫及技术复核修正；产品 `team/`、`core/`、`tools/` 代码未改动。
- `.venv/Scripts/python.exe -B -m pytest tests/team/test_architecture.py tests/team/test_phase6_integration.py -q -p no:cacheprovider`：32 passed；`.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider`：364 passed。文档相对链接、待审状态和 `git diff --check` 已检查；真实模型 smoke 未运行。

Handoff:
- [`Human_Review.md`](Human_Review.md) 是待人工接受的 TASK-07 完成审阅；接受前 TASK-07 保持当前任务，Phase 6 与新增检查项维持 `[ ]`。
- 测试实现已提交为 `8a6198c0cb3489953779a5fb95e75b9f3c5a3195`；完成审阅接受且核对真实结束提交后，才将 TASK-07 移入 `Completed Tasks` 并填写提交引用。

# Completed Tasks

| Task | Outcome | End commit | History |
|---|---|---|---|
| TASK-01 Existing Code Gap Analysis | Done / Phase1 GO | `f90561fff98dcc86ec4261b38e6c32f04c9a9f96` | _history/TASK-01_*.md |
| TASK-02 Team Core Contract Implementation & Composition | Done / Phase 1 complete | `70825632e033e64778d5373d6d8da2b619a56ad8` | _history/TASK-02_*.md |
| TASK-03 Spawn Vertical Slice | Done / Phase 2 complete | `f8c76c4611e582e99245c9638f3dc5206db3e868` | _history/TASK-03_*.md |
| TASK-04 Messaging Vertical Slice | Done / Phase 3 complete | `b007aa4be943ed6fa6ebade27b7f08a18cd94076` | _history/TASK-04_*.md |
| TASK-05 Task Collaboration | Done / Phase 4 complete | `fbed4f01d15fd0e48c30480d0104f731ec9437f9` | [Completion report](_history/TASK-05_completion.md) / [Accepted review](_history/TASK-05_completion-review.md) |
| TASK-06 Shutdown / Teardown / Failure Closure | Done / Phase 5 complete | `b17eb85400e98bf2b6cb51387dfd805bafc3a547` | [Completion report](_history/TASK-06_completion.md) / [Accepted review](_history/TASK-06_completion-review.md) |
