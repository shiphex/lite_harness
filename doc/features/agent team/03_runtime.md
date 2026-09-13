# 1. 模块的运行时设计

## 1.1 TeamAgent 创建路径
``` text
MasterAgent
    │
    │ spawn_teammate(agent_name)
    ▼
Master-only Team Tool (bound to TeamRuntime)
    │
    ▼
TeamCoordinator
    │
    │ spawn_teammate(parent_runtime, agent_name)
    ▼
LifecycleManager
    │
    ├── RuntimeFactory.create(...) → AgentRuntime
    ├── create passive TeamAgent wrapper
    ├── MemberRegistry.register(actual runtime metadata) → STARTING
    ├── retain wrapper / runtime ownership
    └── MemberRegistry.transition(SPAWN_SUCCESS) → IDLE (commit)
```

注意：只有 LifecycleManager 可以创建 TeamAgent 使用的 AgentRuntime。spawn 的 commit point 是 member 成功发布为 IDLE；spawn 本身不启动后台线程、不注入 prompt，也不调用模型。


关键 alternate flow：
``` text
spawn
├ success → runtime → wrapper → STARTING → owned → IDLE commit
└ failure(commit 前)
   ├ reverse cleanup lifecycle-owned wrapper / runtime references
   ├ STARTING record → unregister(reason=SPAWN_ROLLBACK)
   └ no member / no lifecycle-owned worker

详见 F-SPAWN-01 / F-SPAWN-02
```

当前 AgentRuntime 没有 `destroy()` / `close()` contract，因此 rollback 只保证逻辑资源与 ownership 清理；RuntimeFactory 已创建的 filesystem diagnostic artifacts 可以保留。

TeamAgent 的 Phase-2 execution boundary：

``` text
TeamAgent.run(prompt)
    → USER_PROMPT_SUBMIT hook
    → append prompt to its own runtime state/history
    → AgentRuntime.begin_run()
    → existing query_loop(AgentRuntime)
```

谁触发 `run`、是否需要后台线程、以及执行期间的 MemberState 协调，延后到 Phase 3～5；Phase 2 只用 fake loop 验证该边界。

## 1.2 单个 team agent 生命周期示例
``` text
STARTING
   ↓ spawn_success / commit
IDLE
   ↓
BUSY ↔ WAITING
   ↓
IDLE
   ↓ shutdown 
STOPPED

BUSY/WAITING/IDLE
   ↓ fatal_runtime_error
FAILED(record failure / emit event)

IDLE/BUSY/WAITING
   ↓ shutdown
STOPPED

FAILED
   ↓ shutdown / cleanup
FAILED
```

team agent 的 State Machine 转移表：
| Current | Event | Guard | Next | Side Effect |
|---|---|---|---|---|
| STARTING | spawn_success | registered | IDLE | emit started |
| IDLE | task_claimed | task valid | BUSY | execute task |
| BUSY | dependency_wait | dependency exists | WAITING | create_task, update_task |
| WAITING | dependency_resolved | — | BUSY | resume |
| BUSY | task_finished | — | IDLE | publish result |
| IDLE/BUSY/WAITING | shutdown | can_stop | STOPPED | record terminal state / emit stopped |
| IDLE/BUSY/WAITING | fatal_runtime_error | — | FAILED | record failure / emit event |

触发权限表：
| Event | Authority |
|---|---|
| spawn_success | LifecycleManager |
| task_claimed | MasterAgent 分配任务给 TeamAgent |
| dependency_wait | TeamAgent |
| dependency_resolved | TaskStore/Coordinator |
| task_finished | TeamAgent |
| shutdown | TeamCoordinator/LifecycleManager |
| fatal_runtime_error | LifecycleManager/runtime supervisor |

表中的 Authority 表示谁可以请求或报告 transition；MemberRegistry 是唯一实际校验、应用并保存 MemberState 的 authoritative owner。所有状态变化必须通过其受控状态转换接口，非法 transition 必须被拒绝且保持原状态不变。

`STARTING` record 由 `register()` 创建；只有 LifecycleManager 可以提交 `spawn_success`。IDLE 表示 spawn 已完成并可被后续能力使用，不表示 TeamAgent 已开始执行任务。

正常 shutdown 后的 STOPPED record，以及 fatal runtime error 后的 FAILED record，在 TeamRuntime 生命周期结束前必须仍可通过 MemberRegistry 查询。`unregister` 不属于正常 shutdown 或 fatal transition 的副作用，仅用于 spawn 发布成功前的 rollback，或 TeamRuntime 最终释放。


## 1.3 TaskStore 中任务被认领路径
``` text
TeamAgent B
    ↓ create/update task
TaskStore

MasterAgent
    ↓ inspect task
TaskStore

MasterAgent
    ↓ decide assignment
TaskStore.claim/assign(...)

MasterAgent
    ↓ notify
MessageBus
```

以上 Team 路径操作 TeamRuntime 持有的 team-scoped TaskStore。现有 task-system operation 通过显式 store 注入复用；未显式注入时仍保留绑定全局 `TASKS` 的既有工具路径。具体采用函数参数、bound handler 或薄 adapter，延后到对应 Phase 决定。

相关函数(已经在 task_system 中实现)：
``` python
create_task: 创建任务
update_task: 使用返回的 ID 添加任务依赖
can_start: 依赖检查
claim_task: 认领任务
complete_task: 完成与解锁
get_task: 查看完整细节

# pending ──claim──→ in_progress ──complete──→ completed
```

task store 的 State Machine 转移表：
| Current | Event | Guard | Next | Side effect |
|---|---|---|---|---|
| ABSENT | create | valid spec | PENDING | persist task |
| PENDING | claim | can_start && unowned | IN_PROGRESS | set owner |
| IN_PROGRESS | complete | owner matches | COMPLETED | unlock dependents |


## 1.4 MessageBus 示例
``` text
Agent A
   │
   │ send(B, message)
   ▼
MessageBus
   │
   │ enqueue
   ▼
Mailbox[B]

Agent B
   │
   │ receive()
   ▲
   └──────── Mailbox[B]
```

失败路径：
``` text
send
├ success → enqueue
├ failure → target missing → reject
└ failure → mailbox full → reject/backpressure

详见：F-MSG-01 / F-MSG-02
```


# 2. Team 生命周期示例
``` text
MasterAgent
    ↓ spawn
TeamCoordinator
    ↓
LifecycleManager
    ↓
TeamAgent

MasterAgent
    ↓ assign
TeamCoordinator / TaskStore
    ↓
TeamAgent

TeamAgent ↔ MessageBus ↔ TeamAgent

MasterAgent
    ↓ teardown
TeamCoordinator
    ↓
LifecycleManager
```
具体细节见 1.1～1.4 中的示例。
