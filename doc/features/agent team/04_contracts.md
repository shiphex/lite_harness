# 1. 建议代码目录（非架构约束）
``` shell
team/
    agent.py
    coordinator.py
    lifecycle.py
    registry.py
    messaging.py
    tasks.py
    contracts.py
    runtime.py

tools/
    team.py
```

该目录仅表达职责拆分，不固定 TeamRuntime 的代码落点。Phase 1 应根据现有 package convention 选择最小且职责清晰的位置；如果没有合适的已有模块，允许新增 `team/runtime.py`。

# 2. code contract

## 2.1 MailboxHandle Contract
`TeamMessage(sender_id: str, target_id: str, content: str)` 是不可变消息。ID 为实际 AgentRuntime `agent_id`，必须与 Registry 中的规范 ID 完全一致（不接受首尾空白）；content 是非空文本，最多 16,384 字符。

- `MailboxHandle.send(target_id: str, content: str) -> None`
- `MailboxHandle.receive() -> TeamMessage | None`；`None` 表示 mailbox 为空，不阻塞。

LifecycleManager 为 TeamAgent 绑定 sender_id；send 不接受 sender_id 参数。TeamAgent 只能通过自身 handle 使用 MessageBus，不持有或修改 mailbox storage。


## 2.2 TaskStore Protocol
TaskStore 需要的函数：
复用现存的 task_system, Agent Team 需要:
    create_task
    update_task
    can_start
    claim_task
    complete_task
    get_task

TaskStore 集成约束：
- 每个 TeamRuntime 使用独立的 team-scoped TaskStore。
- Team 路径必须将该 store 显式注入现有 task-system operation；具体采用函数参数、bound handler 或薄 adapter，延后到对应 Phase 决定。
- 未显式注入 store 的现有工具调用继续使用全局 `TASKS`，保持向后兼容。
- 不复制第二套 task state、task transition 或 task behavior，也不引入 Scheduler。

Phase-4 team operation：`claim_task_strict(task_id, owner, *, store) -> Task` 与 `complete_task_strict(task_id, owner, *, store) -> TaskCompletion` 通过 typed `TaskError` 子类报告冲突；`TaskCompletion` 包含已完成任务与解锁的任务主题。同一进程同一 TaskStore 的创建、读取、依赖更新、领取和完成受同一可重入锁保护。旧 `claim_task` / `complete_task` 文本接口继续由严格入口适配，默认全局 `TASKS` 路径不变。不承诺跨进程文件事务。

Phase-5 显式恢复使用 `reassign_failed_task_strict(task_id, expected_owner, new_owner, *, store)`：调用方先确认原 owner 为本团队 FAILED 成员；TaskStore 在同进程锁内校验 `in_progress` 与预期 owner，并一次保存新 owner 及 `reassignments` 交接记录。记录依序包含 `from_owner`、`to_owner` 和 `reason: "source_failed"`；旧任务文件缺少该字段时默认为空列表。交接写入以同目录临时文件替换，失败时原任务文件保持完整；不改变任务 ID、状态或依赖，不扩展跨进程事务承诺。


## 2.3 MessageBus Protocol
MessageBus 需要的函数：
- Public:
  - `send(*, sender_id: str, target_id: str, content: str) -> None`
  - `receive(agent_id: str) -> TeamMessage | None`
- Private:
  - _enqueue


图表示逻辑消息路径；Agent 实际通过 MailboxHandle 使用该能力，不直接访问 MessageBus 内部 mailbox。

`MessageBus(registry: MemberRegistry, *, capacity: int = 100)` 只查询所属 TeamRuntime 的 Registry；capacity 必须是正整数。每个 mailbox 是同步加锁的内存 FIFO 队列，按需创建；send / receive 分别在 bus 内原子执行。Phase 5 要求状态检查及队列操作与 shutdown / fatal transition 共享顺序边界：转换之前完成的消息可以留在队列，之后的收发必须拒绝；mailbox 直到 TeamRuntime 最终释放才清空。空队列返回 `None`，满队列立即抛 `MailboxFullError` 且原队列不变；不阻塞、不重试、不持久化。

不存在的 target 抛 `MessageTargetNotFoundError`。不存在或处于 STARTING / STOPPED / FAILED 的 sender，以及处于这些状态的 target，抛 `MessageUnavailableError`。IDLE / BUSY / WAITING 成员可收发。无效 content 抛 `InvalidMessageError`；上述错误均继承 `TeamError`。消息操作不调用 `MemberRegistry.transition()`。


## 2.4 LifecycleManager Protocol
LifecycleManager 需要的函数：
- `spawn(*, parent_runtime: AgentRuntime, agent_name: str) -> MemberRecord`
- `shutdown(agent_id: str) -> MemberRecord`
- `report_fatal(agent_id: str, error: str) -> status result`
- `member_status(agent_id: str) -> status result`
- `teardown() -> result`（Coordinator 向 Master 暴露结果）

Phase-2 `spawn` contract：
- LifecycleManager 是 TeamAgent AgentRuntime 的唯一创建入口。
- 使用 RuntimeFactory 返回的实际 `agent_id` / `agent_name` 注册 MemberRegistry。
- 创建并持有被动 TeamAgent wrapper / AgentRuntime 的逻辑 ownership。
- Registry `STARTING → IDLE` 是 commit；commit 前失败按 `05_failures.md` 逆序 rollback。
- 失败使用 `SpawnError(TeamError)`；不得 silent failure。
- Phase 5 的正常 shutdown 校验当前没有活动 turn、原 owner 未完成任务或待修复的成员收尾；否则返回 typed failure，保留 wrapper、Registry 状态与任务 owner。重复停止保持同一终态。
- `report_fatal` 只用于明确不可恢复的 runtime 故障；普通 query loop 异常沿用 Phase 4 的 BUSY / 原 owner 续跑。fatal 保留 FAILED record 与错误摘要，不凭普通异常自动分类。
- teardown 对各成员 best-effort 处理并汇总失败；失败时不最终释放 TeamRuntime。即使成员已明确 FAILED，只要原 owner 仍有 `in_progress` 任务，正常退出也返回部分失败并保留故障现场。全部安全停止后才通过 `TEAM_RELEASE` 移除 record 并清空 mailbox，TaskStore 文件保留；重复 teardown 幂等。最终释放的 registry/mailbox 清理失败时须恢复此前已接受的 mailbox 与终态 record 供重试。


## 2.5 MemberRegistry Protocol
MemberRegistry 需要的函数：
- `register(agent_id: str, agent_name: str) -> MemberRecord`
- `unregister(agent_id: str, *, reason: UnregisterReason) -> MemberRecord | None`
- `get(agent_id: str) -> MemberRecord`
- `get_member_state(agent_id: str) -> MemberState`
- `list() -> tuple[MemberRecord, ...]`
- `transition(agent_id: str, event: MemberEvent, *, source: TransitionSource) -> MemberRecord`
- `release_all(*, reason: UnregisterReason) -> tuple[MemberRecord, ...]`（仅在全部成员进入终态后一次性移除）

相关 contract types：
- `MemberRecord` 是 immutable member snapshot，以 `agent_id` 为 registry key，并保存 `agent_name` 与 `MemberState`。
- `MemberState`：`STARTING`、`IDLE`、`BUSY`、`WAITING`、`STOPPED`、`FAILED`。
- `MemberEvent` 与 `TransitionSource` 对应 `03_runtime.md` §1.2 的状态机和触发权限表。
- `UnregisterReason` 仅包含 `SPAWN_ROLLBACK` 与 `TEAM_RELEASE`。

受控状态转换操作必须：
- 只接受授权模块发起的 transition 请求或状态报告。
- 根据 `03_runtime.md` 的状态机校验并原子地应用 transition。
- 拒绝非法 transition，且不得改变原 member state。
- 在正常 shutdown 后保留可查询的 STOPPED record，在 fatal error 后保留可查询的 FAILED record。

`unregister()` 仅允许用于：
- spawn 发布成功前的 rollback。
- TeamRuntime 最终释放。

`SPAWN_ROLLBACK` 只能移除 `STARTING` record；`TEAM_RELEASE` 表示 TeamRuntime 最终释放边界。对不存在 member 的 unregister 保持幂等。

MemberRegistry 不应存在的函数：
- spawn()


## 2.6 TeamAgent Contract

- `TeamAgent(runtime: AgentRuntime, mailbox_handle: MailboxHandle)` 是被动 execution wrapper，不创建 AgentRuntime；handle 由 LifecycleManager 用实际 `agent_id` 绑定。
- `TeamAgent.run(prompt) -> existing query_loop result`。
- 每个 TeamAgent 有独立 AgentRuntime / state / history / identity / runtime paths，与 Master 共享 session_id 和当前 workspace。
- TeamAgent 不直接与用户交互。

Phase-2 provisional execution policy：
- parent model / fallback model 的副本；
- `NonInteractiveInteraction` 与 `NullEventSink`；
- `READ_ONLY` memory，namespace 为 `master`；
- tools 为 `read_file` / `glob` / `load_skill`；
- `max_turns=30`。

以上 policy 是 Phase-2 mechanism，不是 architecture invariant；正式 memory namespace、tool capability、event routing 与 max-turn policy 在进入执行能力时重新裁决。

Phase 4 允许 TeamAgent 使用现有 `bash`、`write_file`、`edit_file`，并增加绑定所属 TeamRuntime TaskStore 的 `get_team_task`、`create_team_task`、`update_team_task`、`complete_team_task`。TeamAgent 的 `bash` 仅允许前台执行；其 RunPolicy 禁止启动后台命令和读取进程全局的后台结果队列，避免跨 runtime 泄漏。这些团队任务工具从 `ToolContext.runtime` 验证 wrapper 身份；完成工具仅接受当前执行轮的任务 ID，以实际 `agent_id` 完成任务，再由 TeamAgent 来源提交 `TASK_FINISHED`。不暴露自主 claim。

Phase 3 在既有只读工具之外，仅给 TeamAgent per-instance policy 增加 `send_team_message(target_id, content)` 和 `receive_team_message()`。Handler 从 `ToolContext.runtime` 查找 LifecycleManager 持有的 wrapper，验证 runtime 对象身份后使用其 handle；成功发送返回 JSON `{"status":"sent"}`，接收返回 JSON `{"message": ...}`（空队列为 `null`），typed domain error 转为含异常类型名的明确工具错误文本。工具不加入 Master / 普通 Subagent 的通用集合。工具调用或消息收发不自动触发 TeamAgent 执行。


# 3. 架构和运行时 Contract

## 3.1 TeamCoordinator Contract
use-case API：
- `spawn_teammate(*, parent_runtime: AgentRuntime, agent_name: str) -> MemberRecord`
- shutdown_teammate(...)
- teardown_team(...)
- report_fatal(...) / get_member(...)
- recover_failed_task(task_id, *, parent_runtime: AgentRuntime)
- assign_task(...)

`spawn_teammate` 只负责编排并委托 `LifecycleManager.spawn(...)`；Coordinator 不直接创建 runtime、不持有 worker，也不调用 LLM。Phase 5 的 `shutdown_teammate` 委托 LifecycleManager，`teardown_team` 汇总逐成员停止与释放结果；活动任务不得通过正常停止遗留为不可续跑。任务分配与续跑沿用 Phase 4 契约。


## 3.2 TeamRuntime Invariants
每个 TeamRuntime：
- exactly one MemberRegistry
- exactly one MessageBus
- exactly one TaskStore
- exactly one LifecycleManager
- exactly one TeamCoordinator
- 负责组装并持有上述 team-scoped shared services；允许直接或通过组装关系间接持有
- services 在整个 team 生命周期内共享
- 与 AgentRuntime 保持独立，不并入 AgentRuntime，也不共享二者的状态所有权
- 一个 Master session 对应一个 TeamRuntime；两者由同一 composition scope 创建并共享显式 session_id
- TeamRuntime 在 Master session 建立时即存在，Master 的 per-instance bound tool handler 引用它
- session-scoped TaskStore 路径为 `.agents/runs/<session_id>/tasks`


## 3.3 Master Team Tool Contract

- `spawn_teammate` 只注入 MasterAgent instance 的 allowed tool set / handler binding，不加入通用工具集合，也不暴露给 TeamAgent 或普通 Subagent。
- Phase 4 以相同 per-instance binding 增加 `create_team_task(subject, description="")`、`list_team_tasks()`、`get_team_task(task_id)`、`assign_team_task(task_id, agent_id)`、`resume_team_task(task_id, agent_id)`；它们校验调用 session 并仅使用当前 TeamRuntime。分配与续跑同步返回 JSON，包含 `status`、`task_id`、`agent_id`、`task_status`、`member_state`、`run_reason` 和可选错误。成功的团队任务读写工具返回 JSON；可预期错误返回含类型名的明确文本。
- handler 从 `ToolContext` 取得调用方 Master AgentRuntime，并调用 `TeamCoordinator.spawn_teammate(...)`。
- `create_master_runtime()` 只提供通用的 per-instance tool definition / handler 注入 seam，不依赖或持有 TeamRuntime。

Phase 5 通过同一 Master-only binding 增加 `shutdown_teammate(agent_id)`、`teardown_team()`、`report_team_fatal(agent_id, error)` 与 `get_team_member(agent_id)`。工具校验当前 session，返回实际 member / task 状态与失败原因；可预期的拒绝不报告成功。正常 `q/exit` 调用 teardown；若有未完成任务或其他停止失败，向 Master 报告并保持会话。可运行的原 owner 显式续跑；FAILED owner 的任务按下述恢复入口交接给新成员。任务完成或故障修复后重试退出。最终释放后，除重复 teardown 外的团队工具拒绝操作。

`recover_failed_team_task(task_id)` 也只绑定 Master：仅处理 FAILED owner 的 `in_progress` 任务，自动创建名称为 `recovery_<task_id>` 的全新 TeamAgent，返回新 `agent_id`、原 owner 与实际任务/成员状态。交接前失败不得改写原任务；交接后成员转换失败须保留新 owner 和可续跑入口。普通执行异常仍只允许原 owner 续跑，恢复不会使用现有 IDLE 成员或复制失败成员的聊天历史。



