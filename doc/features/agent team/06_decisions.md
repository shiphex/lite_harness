# 1. ADR 必须包含的内容

ADR 需要：
- Status
- Context
- Decision
- Alternatives
- Consequences


# 2. ADR 项目

## ADR-001 TeamRuntime 与 TeamCoordinator 的关系

Status:
Accepted

Context:
Team-scoped shared services 需要明确的 composition root，同时必须避免把全部职责集中到 TeamCoordinator，或把 Team 状态并入单个 Agent 的 AgentRuntime。

Decision:
- TeamRuntime 是 team composition root，负责组装并持有 team-scoped shared services。
- TeamCoordinator 是 orchestration layer，不拥有所有服务的内部职责。
- TeamRuntime 与 AgentRuntime 保持独立；前者属于 Team，后者属于单个 Agent。
- 具体代码落点不是 architecture invariant。

Alternatives:
- 将 TeamRuntime 并入 AgentRuntime：拒绝，二者的作用域和状态所有权不同。
- 由 TeamCoordinator 直接承担 composition root 及全部服务职责：拒绝，会推动 Coordinator 演化为 God Object。
- 使用独立 TeamRuntime：接受。

Consequences:
- Coordinator、Registry、MessageBus、TaskStore、LifecycleManager 由 TeamRuntime 直接或通过组装关系间接持有。
- Phase 1 按现有 package convention 和单一职责选择最小落点；没有合适模块时允许新增 `team/runtime.py`。

Deferred:
- TeamRuntime 的具体文件位置延后到 Phase 1 决定。

Review source: [_history/TASK-01_human-review.md DD-01](_history/TASK-01_human-review.md#dd-01)


## ADR-002 MemberState 的所有权与终态保留

Status:
Accepted

Context:
授权模块可以请求或报告状态变化，但现有设计缺少由 MemberRegistry 统一校验并应用 transition 的闭环；如果 shutdown 或 fatal 后立即删除记录，也无法观察终态。

Decision:
- MemberRegistry 是 MemberState 的唯一 authoritative owner。
- 所有 MemberState 变化必须经过 MemberRegistry 的受控状态转换接口。
- STOPPED / FAILED member record 在 TeamRuntime 生命周期结束前保持可查询。
- `unregister` 仅用于 spawn 发布成功前的 rollback，或 TeamRuntime 最终释放。

Alternatives:
- 允许 Agent 或 LifecycleManager 直接写状态：拒绝，会形成多个状态真相源。
- 进入终态后立即 unregister：拒绝，会丢失生命周期和失败可观察性。
- 由 MemberRegistry 集中校验、保存并保留终态：接受。

Consequences:
- 授权模块只负责发起 transition 请求或状态报告，MemberRegistry 负责校验和应用。
- 非法 transition 被拒绝且保持原状态不变。
- 正常 shutdown 后可查询 STOPPED，fatal error 后可查询 FAILED。

Deferred:
- 受控状态转换接口的名称、数量和签名延后到 Phase 1 决定。

Review source: [_history/TASK-01_human-review.md DD-02](_history/TASK-01_human-review.md#dd-02)


## ADR-003 Team-scoped TaskStore 与现有工具兼容

Status:
Accepted

Context:
现有 task_system 的能力分散在 TaskStore instance 与绑定全局 `TASKS` 的 module functions 中，与 TeamRuntime-owned、可注入 TaskStore 的设计不一致。

Decision:
- 每个 TeamRuntime 使用独立的 team-scoped TaskStore。
- 复用现有 task state 和 task behavior，不复制第二套任务实现。
- 现有 task-system operation 增加显式 store 注入，同时保留未注入时使用全局 `TASKS` 的工具路径兼容性。
- 不引入 TaskScheduler。

Alternatives:
| 方案 | 复用 | Team 隔离 | 兼容旧代码 | 新复杂度 | 结论 |
| --- | --- | --- | --- | --- | --- |
| 显式 store 注入 | 高 | 高 | 高 | 中 | 接受 |
| 重写 TeamTaskStore | 低 | 高 | 高 | 高 | 拒绝 |
| 所有 TeamRuntime 共用全局 TASKS | 高 | 低 | 高 | 低 | 拒绝 |

Consequences:
- 不同 TeamRuntime 的任务状态相互隔离。
- 原有全局任务工具行为保持兼容。
- Team 集成需要提供显式 store 的绑定点，但不得重复 task logic。

Deferred:
- 最终采用函数参数、bound handler 或薄 adapter，结合 Phase 1 / Phase 4 的代码落点决定。

Review source: [_history/TASK-01_human-review.md DD-03](_history/TASK-01_human-review.md#dd-03)



- [Accepted] ADR-004
Mailbox ownership？
Decision:
    由 MessageBus 管理 mailbox。

Reason:
    若 Agent 管理 mailbox，管理时不易集中。

Consequence:
    MessageBus 管理 mailbox


- [Accepted] ADR-005
TeamAgent shutdown policy？

Context
需要确定 TeamAgent 生命周期结束条件。

Options
A explicit shutdown
B team teardown
C idle timeout
D budget exhaustion

Decision
MVP only A + B.

Consequences
+ 简单、确定性强
+ 容易测试
- 暂时不会自动回收 idle worker

Deferred
idle timeout 留待后续。



- [Accepted] ADR-006
Message semantics:
one-message-one-turn vs conversation session？

Context
需要确定 一条消息 BUSY 然后再 IDLE，一次还是整个聊天期间一直 BUSY。

Options
A one-message-one-turn
B conversation session

Decision
A one-message-one-turn


Consequences
+ 简单、确定性强
+ 容易测试
- 暂时不实现 conversation session


