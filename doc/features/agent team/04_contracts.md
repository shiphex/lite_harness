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
MailboxHandle
    send(...)
    receive(...)


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


## 2.3 MessageBus Protocol
MessageBus 需要的函数：
- Public:
  - send
  - receive
- Private:
  - _enqueue


图表示逻辑消息路径；Agent 实际通过 MailboxHandle 使用该能力，不直接访问 MessageBus 内部 mailbox。


## 2.4 LifecycleManager Protocol
LifecycleManager 需要的函数：
- `spawn(*, parent_runtime: AgentRuntime, agent_name: str) -> MemberRecord`
- shutdown()
- teardown()

Phase-2 `spawn` contract：
- LifecycleManager 是 TeamAgent AgentRuntime 的唯一创建入口。
- 使用 RuntimeFactory 返回的实际 `agent_id` / `agent_name` 注册 MemberRegistry。
- 创建并持有被动 TeamAgent wrapper / AgentRuntime 的逻辑 ownership。
- Registry `STARTING → IDLE` 是 commit；commit 前失败按 `05_failures.md` 逆序 rollback。
- 失败使用 `SpawnError(TeamError)`；不得 silent failure。
- `shutdown()` / `teardown()` 的行为留到 Phase 5，Phase 2 不提前实现。


## 2.5 MemberRegistry Protocol
MemberRegistry 需要的函数：
- `register(agent_id: str, agent_name: str) -> MemberRecord`
- `unregister(agent_id: str, *, reason: UnregisterReason) -> MemberRecord | None`
- `get(agent_id: str) -> MemberRecord`
- `get_member_state(agent_id: str) -> MemberState`
- `list() -> tuple[MemberRecord, ...]`
- `transition(agent_id: str, event: MemberEvent, *, source: TransitionSource) -> MemberRecord`

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

- `TeamAgent(runtime: AgentRuntime)` 是被动 execution wrapper，不创建 AgentRuntime。
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


# 3. 架构和运行时 Contract

## 3.1 TeamCoordinator Contract
use-case API：
- `spawn_teammate(*, parent_runtime: AgentRuntime, agent_name: str) -> MemberRecord`
- shutdown_teammate(...)
- teardown_team(...)
- assign_task(...)

`spawn_teammate` 只负责编排并委托 `LifecycleManager.spawn(...)`；Coordinator 不直接创建 runtime、不持有 worker，也不调用 LLM。其余 API 的具体行为留到对应 Phase。


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
- handler 从 `ToolContext` 取得调用方 Master AgentRuntime，并调用 `TeamCoordinator.spawn_teammate(...)`。
- `create_master_runtime()` 只提供通用的 per-instance tool definition / handler 注入 seam，不依赖或持有 TeamRuntime。



