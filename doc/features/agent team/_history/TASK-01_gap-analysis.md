# TASK-01 Existing Code Gap Analysis

Status: Archived / Non-authoritative
Task: TASK-01 Existing Code Gap Analysis
Baseline: `f90561fff98dcc86ec4261b38e6c32f04c9a9f96`
Outcome: Human reviewed
Source of Truth: `../01_problem.md` through `../08_tasks.md`

---

## 1. Baseline

- Branch：`feature/team`
- HEAD：`f90561fff98dcc86ec4261b38e6c32f04c9a9f96`
- 执行前工作区：clean
- 测试命令：`uv run pytest -q`
- 实际结果：`210 passed in 2.56s`
- 执行后工作区：clean，HEAD 未变化
- 检查范围：当前分支、01–08 设计文档，以及针对 Phase 1 未决问题定向检查的 `feature/agent_teams` 符号
- 仓库修改：无

## 2. Current Facts Validation

| Fact | 结果 | 代码证据 | 结论 |
|---|---|---|---|
| CF-01 | `confirmed` | [core/runtime.py:113](</E:/Workplace/Learn_project/lite_harness/core/runtime.py:113>) | `AgentRuntime` 已存在，并由 `RuntimeFactory` 创建。 |
| CF-02 | `confirmed` | [core/agent.py:147](</E:/Workplace/Learn_project/lite_harness/core/agent.py:147>)、[tools/subagent.py:167](</E:/Workplace/Learn_project/lite_harness/tools/subagent.py:167>) | 当前 MasterAgent 和 Subagent 均直接调用统一 `query_loop`。 |
| CF-03 | `confirmed` | [tools/task_system.py:96](</E:/Workplace/Learn_project/lite_harness/tools/task_system.py:96>)、[tools/task_system.py:195](</E:/Workplace/Learn_project/lite_harness/tools/task_system.py:195>)、[tools/task_system.py:206](</E:/Workplace/Learn_project/lite_harness/tools/task_system.py:206>) | TaskStore 使用 JSON 文件创建、保存和加载任务。 |
| CF-04 | `confirmed` | [tools/task_system.py:243](</E:/Workplace/Learn_project/lite_harness/tools/task_system.py:243>)、[tools/task_system.py:330](</E:/Workplace/Learn_project/lite_harness/tools/task_system.py:330>)、[tools/task_system.py:352](</E:/Workplace/Learn_project/lite_harness/tools/task_system.py:352>) | claim/complete 是操作全局 `TASKS` 的模块函数；`TaskStore` 实例尚不具备完整 Team 协议。 |
| CF-05 | `confirmed` | 当前代码树不存在 `team/`，`core/`、`tools/`、`tests/` 中未找到 `MemberRegistry` | 当前无 team-level registry。 |
| CF-06 | `confirmed` | 当前代码中未找到 `MailboxHandle` 或 `MessageBus` | 当前无 mailbox abstraction。 |

DC-01、DC-02 与现有代码及设计一致：TeamAgent 应通过配置现有 `AgentRuntime` 获得能力，不应引入第二套 Runtime；实际执行继续复用 `query_loop`。

## 3. Component Inventory

| Component | 分类 | 当前证据与缺口 | Contract / Target Phase |
|---|---|---|---|
| AgentRuntime / RuntimeFactory | `reuse` | Factory 支持注入 `session_id`、EventSink、Interaction，并为每个 Runtime 生成独立 `agent_id`；无需新 Runtime 类型。[core/runtime.py:143](</E:/Workplace/Learn_project/lite_harness/core/runtime.py:143>) | DC-01/02；Phase 1/2 |
| TeamRuntime | `new` | 当前无实现；设计要求其持有五个共享服务，但预定目录没有说明其代码落点。 | ADR-001、Contract 3.2；Phase 1 |
| TeamCoordinator | `new` | 当前无实现；只应编排 use case，不持有内部状态或创建 Runtime。 | Contract 3.1；Phase 1 建立边界，Phase 2–5 实现用例 |
| LifecycleManager | `new` | 当前无实现；`RuntimeFactory` 可作为其后续 Runtime 创建依赖。 | Contract 2.4；Phase 1 边界、Phase 2/5 行为 |
| MemberRegistry | `new` | 当前无实现；状态模型已有文档，但缺少受控状态更新接口和终态保留语义。 | ADR-002、Contract 2.5；Phase 1 |
| MessageBus | `new` | 当前无实现。Phase 1 只需确立共享服务位置，不应提前决定容量和投递行为。 | ADR-004、Contract 2.3；Phase 1 shell、Phase 3 行为 |
| MailboxHandle | `new` | 当前无实现；应作为 Agent 的窄能力入口，不能拥有 mailbox storage。 | Contract 2.1；Phase 3 |
| TeamAgent | `adapt` | 复用 AgentRuntime；需在 Spawn 阶段新增 Team 专用 policy、工具和执行包装，不新增 TeamAgentRuntime。 | SC-01/02、DC-01/02；Phase 2 |
| TaskStore integration | `adapt` | 持久化模型可复用，但完整操作仍绑定全局 `TASKS`，与 TeamRuntime-owned service 不匹配。 | Contract 2.2/3.2；Phase 1 边界、Phase 4 行为 |
| Master tool entry | `adapt` | Master policy 当前硬编码全局 `TOOLS_LIST`/`TOOLS_HANDLERS`；ToolExecutor 本身支持每 Runtime 注入 handler。[core/agent.py:49](</E:/Workplace/Learn_project/lite_harness/core/agent.py:49>)、[core/loop.py:348](</E:/Workplace/Learn_project/lite_harness/core/loop.py:348>) | Runtime 1.1、Coordinator 3.1；Phase 2 |

定向旧分支审查结果：

- 可参考：TaskStore 显式 `store=` 注入和 `bind_task_handlers(store)`；终态成员保留在 roster。
- 必须避免：旧 `TeamCoordinator` 同时持有 members、workers、bus、tasks 和 worktree，违反当前 ADR-001/002 及模块边界。
- 不继承：worktree/profile、SessionDriver、等待控制等当前 Spec 未定义能力。

## 4. Phase 1 Blockers

### B-01：TeamRuntime 没有明确代码落点和构造边界

**Invariant:** TeamRuntime 是 composition root，并在 team 生命周期内持有唯一共享服务。

**Evidence:** [02_architecture.md:33](</E:/Workplace/Learn_project/lite_harness/doc/features/agent team/02_architecture.md:33>) 定义 TeamRuntime；[04_contracts.md:3](</E:/Workplace/Learn_project/lite_harness/doc/features/agent team/04_contracts.md:3>) 的目录却没有 `team/runtime.py`。

**Impact:** 下一任务无法明确由哪个模块创建和持有 Coordinator、Registry、MessageBus、TaskStore、LifecycleManager。

**Recommended direction:** 增加 `team/runtime.py`，由 `TeamRuntime` 负责组装并持有共享服务；不要把 TeamRuntime 状态塞进 `AgentRuntime`。

### B-02：MemberRegistry 的状态更新与终态保留契约不闭合

**Invariant:** MemberRegistry 是 MemberState 的唯一所有者，STOPPED/FAILED 必须可观察，跨模块不得直接改状态。

**Evidence:**

- 架构要求 TeamAgent 通过 `report_state(...)`：[02_architecture.md:126](</E:/Workplace/Learn_project/lite_harness/doc/features/agent team/02_architecture.md:126>)
- Registry Contract 没有 `report_state` 或 `transition`：[04_contracts.md:53](</E:/Workplace/Learn_project/lite_harness/doc/features/agent team/04_contracts.md:53>)
- shutdown 转移同时要求 STOPPED 和 unregister：[03_runtime.md:64](</E:/Workplace/Learn_project/lite_harness/doc/features/agent team/03_runtime.md:64>)
- Failure Policy 又要求 fatal failure 具有可观察终态：[05_failures.md:8](</E:/Workplace/Learn_project/lite_harness/doc/features/agent team/05_failures.md:8>)

**Impact:** 如果 unregister 删除记录，就无法查询 STOPPED/FAILED；如果各调用方直接赋值，则违反 ADR-002 和 SC-05。

**Recommended direction:**

- 新增独立 `MemberState`，不要复用 `AgentRuntime.state`。
- 以 `agent_id` 作为 Registry 的规范键，`agent_name` 仅为显示 metadata。
- Registry 提供唯一受控 `transition(agent_id, event)` 入口并执行状态机校验。
- 普通 shutdown 保留终态记录；`unregister` 仅用于未成功发布成员的 rollback 或整个 TeamRuntime 最终释放。

旧分支“保留终态 roster”的思路可以参考，但其状态由 Coordinator 直接持有，不可复制。

### B-03：TaskStore Contract 与现有实例 API 不一致

**Invariant:** TeamRuntime 持有一个可注入的 TaskStore；任务状态不能依赖不可替换的进程级全局对象。

**Evidence:**

- Contract 要求 `create_task/update_task/can_start/claim_task/complete_task/get_task`：[04_contracts.md:20](</E:/Workplace/Learn_project/lite_harness/doc/features/agent team/04_contracts.md:20>)
- 当前 `TaskStore` 实例只有 `create/update_dependencies/save/load/list`。
- 其余操作通过全局 `TASKS` 完成：[tools/task_system.py:243](</E:/Workplace/Learn_project/lite_harness/tools/task_system.py:243>)

**Impact:** 直接把现有 TaskStore 放入 TeamRuntime 不能满足 Contract；在 `team/tasks.py` 复制任务逻辑又会产生第二套状态实现。

**Recommended direction:** 让现有 task-system 操作接受显式 `store`，保留缺省全局 `TASKS` 兼容当前工具；再通过薄 adapter 或 bound handler 把 TeamRuntime 的 TaskStore 实例注入 Team 工具。旧分支的 `store=`/`bind_task_handlers` 模式可定向参考，但不复制其额外调度与 worktree 行为。

## 5. Deferred Questions

这些问题不阻塞 Phase 1：

- Spawn：`run_turn()`、worker/supervisor、Runtime 创建后的 rollback、TeamAgent memory/session 策略。
- Messaging：mailbox capacity、backpressure、STOPPED target、消息事件。
- Task Collaboration：assignment 语义、task owner 使用 `agent_id` 还是显示名称、并发 claim、具体 typed conflict。
- Shutdown：停止超时、幂等、partial teardown failure aggregation。
- 各纵切：具体 typed error/result 类型。
- Integration：SC-06/07 尚未进入 Traceability Matrix；当前也没有专门的 TaskStore 测试文件。

## 6. Design Deltas

### DD-01：补充 TeamRuntime 模块

- 来源：Architecture 定义了 TeamRuntime，但 Contracts 的目录没有其落点。
- 推荐：在目录设计中增加 `team/runtime.py`，承载 composition root。
- 备选：放入 `coordinator.py` 或 `contracts.py`。
- 判断：不推荐备选，会混淆 composition、orchestration 与数据契约。

### DD-02：补齐 MemberRegistry 状态契约

- 来源：`report_state`、Registry Protocol、shutdown/unregister 和终态可观察性互相不闭合。
- 推荐：增加受控 `transition` 接口；shutdown 保留终态记录，rollback/最终释放才 unregister。
- 备选：删除成员并仅依赖 EventSink 保存终态。
- 判断：不推荐备选；事件是发生事实，不应成为 Registry 查询状态的替代存储。

### DD-03：明确 TaskStore 注入策略

- 来源：Contract 使用完整 TaskStore Protocol，现有具体类与全局函数却是两套调用形态。
- 推荐：复用现有存储模型，为操作增加显式 store 注入，并保留全局兼容入口。
- 备选：在 `team/tasks.py` 重写任务行为，或让所有 TeamRuntime 共用全局 `TASKS`。
- 判断：两项备选分别导致逻辑重复和 team scope 泄漏。

### DD-04：修正架构测试中的实际符号名

[07_test_plan.md:36](</E:/Workplace/Learn_project/lite_harness/doc/features/agent team/07_test_plan.md:36>) 写的是 `AgentRuntimeFactory`，实际类名是 `RuntimeFactory`。应修正 ARCH-01，否则后续 import-boundary test 可能检查错误符号。该项不单独阻塞 Phase 1。

## 7. GO/NO-GO for Phase 1

结论：**NO-GO**

技术上不存在不可行因素：现有 RuntimeFactory、query loop、per-runtime ToolExecutor 以及项目中的 `Protocol`/dataclass 惯例足以承载新设计。

当前阻塞来自尚未接受的设计边界：

1. TeamRuntime 的模块位置与 composition responsibility。
2. MemberRegistry 的唯一状态更新入口及终态保留规则。
3. TaskStore 的实例注入与全局兼容策略。

Human 接受 DD-01～DD-03 后，即可转为 GO，并据此展开 `Team Core Contract Implementation & Composition` 的详细任务。DD-04 可随设计文档更新一并修正。

## 8. Handoff

- 本次只提交分析报告，没有修改仓库。
- 执行前后均为同一 HEAD，工作区保持 clean。
- 建议 Human 审阅并决定是否接受 DD-01～DD-04。
- 接受后：
  1. 将 CF-01～CF-06 标记为 `confirmed`。
  2. 将接受的 Design Deltas 更新到 02、03、04、07。
  3. 再展开 Phase 1 的详细任务。
- 在上述决策进入设计文档之前，不建议开始 Phase 1 实现。

**CHANGES REQUESTED**
