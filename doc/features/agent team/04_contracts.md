# 1. 建议代码目录（非架构约束）
``` shell
team/
    coordinator.py
    lifecycle.py
    registry.py
    messaging.py
    tasks.py
    contracts.py
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
- spawn()
- shutdown()
- teardown()


## 2.5 MemberRegistry Protocol
MemberRegistry 需要的函数：
- register()
- unregister()
- get()
- get_MemberState()
- list()
- 受控状态转换操作（具体名称和签名延后到 Phase 1）

受控状态转换操作必须：
- 只接受授权模块发起的 transition 请求或状态报告。
- 根据 `03_runtime.md` 的状态机校验并原子地应用 transition。
- 拒绝非法 transition，且不得改变原 member state。
- 在正常 shutdown 后保留可查询的 STOPPED record，在 fatal error 后保留可查询的 FAILED record。

`unregister()` 仅允许用于：
- spawn 发布成功前的 rollback。
- TeamRuntime 最终释放。

MemberRegistry 不应存在的函数：
- spawn()


# 3. 架构和运行时 Contract

## 3.1 TeamCoordinator Contract
use-case API：
- spawn_teammate(...)
- shutdown_teammate(...)
- teardown_team(...)
- assign_task(...)


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



