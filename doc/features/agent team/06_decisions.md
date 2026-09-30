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


## ADR-007 Spawn commit 与 execution boundary

Status:
Accepted

Context:
Phase 2 需要区分“创建并发布 TeamAgent”与“为 TeamAgent 注入工作并执行”。如果 spawn 同时启动线程或调用模型，会提前引入 messaging、task collaboration 和 supervision 语义。

Decision:
- Spawn 的 commit point 是 member 经 MemberRegistry 从 STARTING 发布为 IDLE。
- Spawn 只创建被动 TeamAgent execution wrapper，不启动后台线程、不立即调用模型。
- TeamAgent 提供 `run(prompt)` 边界，并复用现有 AgentRuntime / `query_loop`。

Alternatives:
- Spawn 后立即执行模型：拒绝，会把创建与任务执行耦合并越过 Phase 2 边界。
- Spawn 后启动常驻 worker：Deferred，等待 messaging / task collaboration 的驱动方式确定。
- 发布被动 wrapper：接受。

Consequences:
- IDLE 表示 member 已发布可用，不表示已开始工作。
- Phase 2 可以通过 fake loop 验证 execution boundary，而无需真实模型。

Deferred:
- `run` 的触发者、后台线程、fatal supervision 与 shutdown 分别留到 Phase 3～5。

Review source: [_history/TASK-03_human-review.md DD-01](_history/TASK-03_human-review.md#dd-01)


## ADR-008 Master session composition 与 TeamRuntime 绑定

Status:
Accepted

Context:
Master AgentRuntime 在启动时创建，而 TeamRuntime 是不同层次的 team composition context；需要在不把 Team 状态塞入 AgentRuntime 的前提下绑定 Master-only team tool。

Decision:
- 一个 Master session 对应一个 TeamRuntime composition context。
- Master AgentRuntime 与 TeamRuntime 是 sibling，不相互拥有状态。
- Master session composition scope 生成 session_id，并显式传给 Master AgentRuntime 与 TeamRuntime。
- composition scope 持有 TeamRuntime，Master 的 bound spawn handler 引用 TeamRuntime。
- `create_master_runtime()` 只提供通用 per-instance tool definition / handler 注入 seam，不感知 TeamRuntime。
- TeamRuntime 在 Master session 创建时建立；第一次 spawn 不负责创建 TeamRuntime。

Alternatives:
- 在 AgentRuntime 增加 TeamRuntime 字段：拒绝，会合并不同 scope 的状态所有权。
- 使用全局 TeamRuntime：拒绝，无法保证 session isolation。
- composition-scope sibling + bound handler：接受。

Consequences:
- TeamAgent 与 Master 共享 session_id，TeamRuntime 的 TaskStore 使用 session-scoped 路径。
- `spawn_teammate` 只需注入 Master instance，不污染通用工具集合。

Deferred:
None

Review source: [_history/TASK-03_human-review.md DD-02](_history/TASK-03_human-review.md#dd-02)


## ADR-009 TeamAgent Phase-2 runtime policy

Status:
Accepted

Context:
TeamAgent 需要可由统一 `query_loop` 使用的独立 AgentRuntime，但正式的 memory、tool、event routing 与 turn policy 尚未进入对应能力阶段。

Decision:
- TeamAgent 有独立 AgentRuntime、state、history、agent_id 与 runtime paths。
- TeamAgent 与 Master 共享 session_id 和当前 workspace，不直接与用户交互。
- Phase 2 默认复制 parent model / fallback model，使用 `NonInteractiveInteraction` 与 `NullEventSink`。
- Phase 2 暂用 READ_ONLY memory（namespace `master`）、`read_file` / `glob` / `load_skill` 和 `max_turns=30`。

Alternatives:
- 复用 Master AgentRuntime/state：拒绝，会破坏每个 Agent 独立状态所有权。
- 在 Phase 2 定义完整 profile / event routing：拒绝，超出当前 vertical slice。
- 使用最小 provisional policy：接受。

Consequences:
- Phase 2 可安全 fake-test TeamAgent execution，不发生用户交互或 child-output routing。
- provisional 值不得被提升为长期 architecture invariant。

Deferred:
- 正式 memory namespace、tool capability、event routing 与 max-turn policy 在真正进入执行能力时重新裁决。

Review source: [_history/TASK-03_human-review.md DD-03](_history/TASK-03_human-review.md#dd-03)


## ADR-010 Spawn ownership 与 rollback

Status:
Accepted

Context:
RuntimeFactory 创建 AgentRuntime 时会创建 runtime directories，但 AgentRuntime 当前没有 `destroy()` / `close()` contract。需要明确创建入口、ownership、commit 和可验证的 rollback 范围。

Decision:
- 调用方向固定为 Tool → TeamCoordinator → LifecycleManager → RuntimeFactory。
- 只有 LifecycleManager 创建 TeamAgent AgentRuntime，并持有 TeamAgent wrapper / AgentRuntime 的逻辑 ownership。
- 创建顺序为 AgentRuntime → wrapper → Registry STARTING → Lifecycle ownership → SPAWN_SUCCESS → IDLE commit。
- commit 前失败时逆序释放逻辑 ownership；已注册 STARTING record 使用 `SPAWN_ROLLBACK` 移除。
- `SpawnError(TeamError)` 表示 spawn domain failure。
- rollback 不承诺删除 RuntimeFactory 已创建的 filesystem diagnostic artifacts。

Alternatives:
- Coordinator 或 TeamAgent 直接创建 runtime：拒绝，会形成多个 lifecycle 入口。
- 要求删除 runtime directories：拒绝，当前缺少通用 runtime destruction contract。
- Lifecycle 单点创建与逻辑 rollback：接受。

Consequences:
- 成功结果是使用 RuntimeFactory 实际 identity 的 IDLE MemberRecord。
- 失败后 Registry 与 LifecycleManager 均不保留本次未发布 member / worker。

Deferred:
None

Review source: [_history/TASK-03_human-review.md DD-04](_history/TASK-03_human-review.md#dd-04)


## ADR-011 Phase-3 messaging protocol 与 TeamAgent capability

Status:
Accepted

Context:
Phase 3 需要在既有被动 TeamAgent 与 team-scoped MessageBus 之间建立可测试的收发路径。ADR-004 已确定 bus 拥有 mailbox，ADR-006 已确定未来执行采用 one-message-one-turn，但容量、成员状态、消息工具与同步边界尚未裁决。

Decision:
- LifecycleManager 用 RuntimeFactory 返回的实际 `agent_id` 创建 MailboxHandle，并注入 TeamAgent wrapper；handle 固定 sender 身份，消息不得由调用者指定 sender。
- 使用不可变 `TeamMessage(sender_id, target_id, content)`；content 为非空文本，最多 16,384 字符。
- MessageBus 仅查询所属 TeamRuntime 的 MemberRegistry，按需创建容量默认 100 条的内存 FIFO mailbox；容量可在构造时配置为正整数。同步 send / receive 由 bus 锁保护，空队列返回 `None`，满队列立即拒绝且原队列不变。
- IDLE / BUSY / WAITING 成员可收发；目标不存在、sender 不存在、STARTING / STOPPED / FAILED 成员、无效 content 和满队列均用 `TeamError` 子类显式拒绝。
- 仅 TeamAgent policy 增加 `send_team_message` / `receive_team_message` 工具。Handler 根据 `ToolContext.runtime` 找到当前 wrapper 并验证对象身份，通过其 handle 收发；Master 与普通 Subagent 不获得这些工具。
- 收发不自动触发 `run()`、模型执行或 MemberState transition；不承诺与未来并发 shutdown 的跨模块原子性。

Alternatives:
- 仅暴露宿主 wrapper API：拒绝，query_loop 中的 TeamAgent 无法使用通信能力。
- 无界队列或阻塞重试：拒绝，难以控制内存占用或验证失败路径。
- 消息到达即启动 TeamAgent：拒绝，超出 Phase 3 的收发边界。

Consequences:
- Phase 3 可以用 fake runtime 与显式工具调用验证消息垂直链路，无需真实模型。
- MessageBus 不拥有 AgentRuntime 或生命周期；跨模块 shutdown 竞态留待 Phase 5。

Review source: [_history/TASK-04_human-review.md DD-01～DD-04](_history/TASK-04_human-review.md)


## ADR-012 Phase-4 显式任务分配与恢复

Status:
Accepted

Context:
Phase 4 需要把 Master 看板、TeamRuntime-owned TaskStore 和既有 TeamAgent.run 连接起来；TASK-05 预检中的 DD-01～DD-05 尚未确定同步触发、工具边界和部分成功处理。

Decision:
- Master 使用专属团队工具创建、查看、分配和显式续跑任务；TeamAgent 使用专属团队任务工具查看、创建、更新依赖与完成，不自主领取。TeamAgent 同时获得现有工作区编辑与前台命令工具；其 runtime 不使用进程全局后台命令队列。
- 团队任务 owner 是实际 `agent_id`。分配同步调用一次 TeamAgent.run，任务指令直接作为 prompt，不向 mailbox 额外通知。
- 同一进程同一 TaskStore 的领取互斥，旧全局工具路径和文本接口兼容；不承诺跨进程原子性。
- 部分成功保留真实任务与成员状态；未完成或执行异常时只允许原 owner 显式续跑。完成后成员状态转换失败时，只重试收尾转换。

Alternatives:
- 分配后只发送消息或启动后台 worker：本阶段不采用；需要额外执行与监督语义。
- 失败后自动退回 pending：本阶段不采用；会掩盖已发生的执行副作用。

Consequences:
- Master 工具调用等待一次 TeamAgent turn；同一成员的任务执行互斥。
- TeamRuntime 仍隔离任务状态；MemberRegistry 仍是成员状态唯一 owner。

Review source: [_history/TASK-05_human-review.md](_history/TASK-05_human-review.md)


## ADR-013 Phase-5 正常停止与 fatal 分类

Status:
Accepted

Context:
Phase 4 的任务由 Master 同步触发，普通执行异常保留 `in_progress` / BUSY 供原 owner 续跑；现有 AgentRuntime 没有强制中断或 close contract。直接停止有任务的成员会留下不可续跑任务，用户明确禁止这种结果。

Decision:
- Master 专属停止入口经 Coordinator 委托 LifecycleManager；MemberRegistry 仍是 MemberState 唯一 owner。成功正常停止保留 STOPPED record 到 TeamRuntime 最终释放；重复停止幂等。
- 活动同步 turn 返回 `StopBusyError`。仍有原 owner `in_progress` 任务，或已完成任务的成员收尾转换未恢复时，拒绝正常停止并保留 wrapper / 状态；Master 让可恢复的原 owner 显式续跑或修复后重试。不自动重置或改派任务；FAILED owner 的后续显式恢复见 ADR-015。
- 正常 `q/exit` 的 teardown 如遇上述停止失败，报告实际状态并拒绝退出，保留会话供恢复。
- 普通 query loop 异常继续按 F-TASK-03 / 04 恢复；只有明确不可恢复的 runtime 故障由 LifecycleManager 报告 `FATAL_RUNTIME_ERROR`，保留 FAILED record、错误摘要与任务事实。

Alternatives:
- 停止 BUSY 成员但保留不可续跑任务：用户拒绝。
- 引入后台 worker、强制中断或自动任务改派：当前同步 runtime 与 TaskStore 契约不支持，本阶段不采用。

Consequences:
- 停止、teardown 与正常退出可能被活动执行或未恢复任务拒绝；调用方必须先处理任务再重试。
- fatal 与普通可恢复执行异常有不同的可观察结果；无法检测的进程崩溃不由此保证自动恢复。

Review source: [_history/TASK-06_human-review.md](_history/TASK-06_human-review.md) DD-01～DD-03 / DD-06


## ADR-014 Phase-5 teardown 与消息终态顺序

Status:
Accepted

Context:
Phase 3 的 MessageBus 只保证单次队列操作原子，与 Registry 的终态转换没有共同顺序；teardown 的部分失败若提前释放 team，会失去终态和任务恢复入口。

Decision:
- Teardown 逐成员 best-effort 停止并汇总失败；任何停止或清理失败都保留 TeamRuntime 及可查询 STOPPED / FAILED record 供重试。全部成员安全停止且逻辑 ownership 清理后才以 `TEAM_RELEASE` 最终释放 Registry record 与内存 mailbox；session TaskStore 文件保留。重复 teardown 幂等。
- 消息状态检查和队列操作与 shutdown / fatal transition 使用共同顺序边界。终态转换前已接受的消息可留到最终释放，转换后的 send/receive 必须拒绝；MessageBus 仍只拥有 mailbox，Registry 仍只拥有 MemberState。

Alternatives:
- Teardown 遇首个失败即中断或静默释放：不满足 best-effort 汇总和可恢复性。
- 只检查一次 Registry 状态而允许随后并发入队：不能保证终态后的消息拒绝。

Consequences:
- Teardown 需要可重试的部分结果；消息与终态转换之间需要可测试的同步边界。
- 内存 mailbox 在最终释放时清空，不提供持久化或跨进程事务。

Review source: [_history/TASK-06_human-review.md](_history/TASK-06_human-review.md) DD-04～DD-05


## ADR-015 FAILED 任务由新 TeamAgent 显式恢复

Status:
Accepted

Context:
FAILED 成员不再有可续跑 wrapper；若仍拥有 `in_progress` 任务，正常 teardown 按 DD-02 拒绝最终释放。现有 IDLE 成员可能有自己的上下文，不应直接接手。

Decision:
- Master 逐项调用 `recover_failed_team_task(task_id)`。仅当任务为 `in_progress` 且原 owner 是本团队 FAILED 成员时，由 LifecycleManager 创建全新 `recovery_<task_id>` TeamAgent；不自动扫描任务，也不使用现有 IDLE 成员。
- TaskStore 在同进程锁内保持任务 ID / 状态 / 依赖，原子保存新 owner 和按顺序追加的 `reassignments` 记录。旧文件缺省空记录；不继承失败成员的聊天历史。新成员使用任务内容和共享工作区，交接成功后同步执行一轮。
- spawn 或交接前失败保留旧 owner，并安全停止已发布但未接任务的新成员；交接后失败保留新 owner / 任务事实，允许其续跑或在再次 FAILED 后重新显式恢复。原 FAILED record 留到 TeamRuntime 最终释放。

Alternatives:
- 使用现有 IDLE 成员接手：用户拒绝，避免影响其上下文。
- 自动改派全部失败任务：与 Master 显式恢复和既有任务边界不符。

Consequences:
- 任务文件新增可选交接记录；正常退出只在所有当前 owner 的任务安全完成后释放团队。
- 新 TeamAgent 拥有独立 AgentRuntime / state / history；共享工作区已有副作用不自动回滚。

Review source: [_history/TASK-06_recovery-review.md](_history/TASK-06_recovery-review.md) CR-02
