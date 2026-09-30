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
| [√] | Phase 6 | Integration / architecture enforcement | SC、ARCH、Failure tests                | Integration / Architecture Enforcement |
| [ ] | Optional Smoke | Real-model E2E smoke | 显式调用真实模型并核对团队任务闭环 | TASK-08 Optional Real-model E2E Smoke |


# Current Facts

维护规则：切换当前任务时，只保留与该任务有关、且有验收证据的代码事实，目标约 7～8 条。

> 下列代码事实于 TASK-08 预检时核对当前实现；既有设计验收见 [`_history/`](./_history/README.md)。

Validated against: `4b575b6c437bdbbf3c82467ebf73b5099724caec` (`feature/team`)，TASK-08 预检开始时工作区干净；全量 pytest 为 364 passed。证据见 [`_history/TASK-08_preflight.md`](_history/TASK-08_preflight.md)。

| ID | Status | Confirmed code fact | Evidence |
| --- | --- | --- | --- |
| CF-01 | `confirmed` | TeamRuntime 组装并持有 Registry、MessageBus、独立 TaskStore、LifecycleManager 与 Coordinator。 | `eb9ed3b/team/runtime.py:27`～`:42` |
| CF-02 | `confirmed` | Master session 创建 sibling TeamRuntime，共享显式 session_id，并将团队工具绑定在 Master 实例。 | `eb9ed3b/core/agent.py:124`～`:137`、`eb9ed3b/tools/team.py:110` |
| CF-03 | `confirmed` | LifecycleManager 是 TeamAgent runtime 的创建入口，持有已发布 wrapper，并按实际 runtime ID 绑定 mailbox handle。 | `eb9ed3b/team/lifecycle.py:87`～`:135`、`:344` |
| CF-04 | `confirmed` | TeamAgent 的 `run(prompt)` 进入既有 `query_loop`；消息工具使用实际 runtime 身份取得绑定 handle。 | `eb9ed3b/team/agent.py:30`～`:58`、`eb9ed3b/team/messaging_tools.py:39`～`:70` |
| CF-05 | `confirmed` | 统一 query_loop 经 adapter factory 发出 ModelRequest；模型配置允许指定 API、URL、密钥与模型名，默认指向本地服务。 | `4b575b6/core/loop.py:455`～`:463`、`4b575b6/api/adapter_factory.py:12`、`4b575b6/config/config.py:62`～`:67` |
| CF-06 | `confirmed` | Team 路径复用显式注入的 TaskStore；未注入 store 的旧路径仍使用全局 `TASKS`。 | `eb9ed3b/team/coordinator.py:73`～`:82`、`eb9ed3b/tools/task_system.py:296`～`:303` |
| CF-07 | `confirmed` | Coordinator 编排分配、原 owner 续跑及 FAILED 任务显式恢复；任务交接由现有 task_system 保存。 | `eb9ed3b/team/coordinator.py:84`～`:109`、`:138`～`:184`、`eb9ed3b/tools/task_system.py:458` |
| CF-08 | `confirmed` | Phase 6 全链路测试使用 fake loop；可选真实模型 smoke 尚无独立入口。 | `4b575b6/tests/team/test_phase6_integration.py:1`、`4b575b6/doc/features/agent team/07_test_plan.md:14` |

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

TASK-08 的 [预检报告](_history/TASK-08_preflight.md) 已准备，用户已接受 [DD-01～DD-03](_history/TASK-08_human-review.md)；下一道门槛是在新对话中按已接受设计实现并显式运行真实模型 smoke，然后准备独立完成审阅。`SMOKE-01` 保持 `[ ]`；本地服务的健康状态和模型列表已读取，真实模型推理与工具调用尚未执行；MVP Phase 0～6 的已接受状态不变。

# TASK-08 Optional Real-model E2E Smoke

Status:
Design Accepted / Ready for Implementation；DD-01～DD-03 已接受，smoke 入口与真实模型调用尚未执行

Goal:
在 Phase 6 已接受的团队契约上，以一次显式启动的真实模型调用验证 TeamAgent 的统一 query_loop、模型适配器、任务完成工具与安全 teardown 能组合运行；该可选任务不改变 MVP 验收。

References:
- REQUIREMENT: `01_problem.md` §2.1 / SC-01～07 与 §3 Non-goal；`07_test_plan.md` §1 Test Strategy 中的 optional real-model smoke
- ARCH / CONTRACT: `02_architecture.md` §2.1～2.6、`04_contracts.md` §2.2 / §2.4 / §2.6 / §3.1～3.3
- ADR / FAILURE: `06_decisions.md` ADR-007 / 008 / 010 / 012～015；`05_failures.md` F-SPAWN、F-TASK、F-STOP
- CURRENT EVIDENCE: 本文 CF-01～08、[TASK-07 完成审阅](_history/TASK-07_completion-review.md)、[TASK-08 预检](_history/TASK-08_preflight.md)、[TASK-08 设计审阅](_history/TASK-08_human-review.md) 与 [SMOKE-01](07_test_plan.md)

Preconditions:
- TASK-07 / Phase 6 已接受并提交，TASK-08 基线为 `4b575b6` 的干净工作区，自动回归为 364 passed。
- 用户启动的 llama.cpp 本地服务在 `http://127.0.0.1:8000` 返回 `/health` 200 和 `/v1/models` 200，模型 ID 为 `unsloth/Qwen3.5-4B-GGUF:UD-Q6_K_XL`。已接受使用 OpenAI-compatible `/v1` 配置与本地无鉴权占位值 `no-key`；尚未验证推理或工具调用。

Allowed scope:
- 增加显式运行、默认不进入 pytest 的真实模型 smoke 入口；使用临时 workspace、现有 TeamRuntime / RuntimeFactory / Master bound handler / TaskStore 与真实 TeamAgent query_loop。
- 用既有团队任务工具执行一项简短任务并检查 owner、完成状态、成员状态与最终释放；`07_test_plan.md` 中的可选 `SMOKE-01` 已增列，完成审阅前保持 `[ ]`。
- 记录配置、调用次数或停止原因等不含密钥的证据，以及无法运行或失败时的实际分类。

Must:
- 运行入口必须显式提供或确认服务配置并限制单次 smoke 的任务数、turn 数与输出 token；真实凭据只从环境变量读取，本地无鉴权服务可使用 README 的 `no-key` 占位值，不输出密钥。
- 经 Master bound 工具创建成员及任务并分配；至少一次 TeamAgent 模型响应必须经统一 query_loop 触发当前任务的 `complete_team_task`，完成后安全 teardown。
- 区分服务/凭据不可用、模型未调用完成工具和运行时失败；只有观察到任务、owner、成员与释放结果均符合契约，才报告 smoke 通过。

Must not:
- 服务配置缺失时不把跳过记为通过；未完成实现与实测时不得勾选 `SMOKE-01` 或声明 TASK-08 完成。
- 不让默认 pytest/CI 自动发起外部请求，不把密钥放入仓库、命令行参数或报告；不修改生产团队契约、已完成的 MVP 检查项或引入 Non-goal 能力。

Design review accepted:
- DD-01：接受显式、可重复的单任务 smoke 入口；Master bound 工具由脚本驱动，真实模型只驱动 TeamAgent 的统一 query_loop。
- DD-02：接受参数化服务配置、临时 workspace、一项任务、最多 3 个 TeamAgent turn 和每次最多 512 个输出 token；本地服务使用 `api=openai`、`model_url=http://127.0.0.1:8000/v1` 与上述模型 ID。
- DD-03：接受真实调用、任务完成、owner / IDLE / teardown 的通过标准及失败分类；`SMOKE-01` 在完成审阅接受前保持 `[ ]`。

Verification plan:
- 实现时检查 smoke 入口的参数校验、密钥不回显与显式启动边界；运行项目全量 pytest，并在可用服务上只执行获批的单次真实模型 smoke。
- 核对任务文件、成员和 teardown 的实际结果；文档链接及 `git diff --check` 通过后准备独立完成审阅。

Handoff:
- [`Human_Review.md`](Human_Review.md) 与[归档审阅](_history/TASK-08_human-review.md)记录已接受的 TASK-08 设计；本次仅提交设计、预检与任务文档，后续实现及实测由新对话继续。
- 运行时使用已探测的本地服务配置，服务发生变化时重新预检；不可提交或展示真实密钥值。

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
