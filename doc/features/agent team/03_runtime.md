# 1. 模块的运行时设计

## 1.1 TeamAgent 创建路径
``` text
MasterAgent
    │
    │ team.spawn(...)
    ▼
Team Tool
    │
    ▼
TeamCoordinator
    │
    │ spawn request
    ▼
LifecycleManager
    │
    ├── create AgentRuntime
    │
    └── MemberRegistry.register(runtime metadata)
```

注意：禁止 TeamAgent 创建 AgentRuntime 实例。


关键 alternate flow：
``` text
spawn
├ success → register → IDLE
└ failure(注册成功前) → rollback → no member 

详见 F-SPAWN-01 / F-SPAWN-02
```

## 1.2 单个 team agent 生命周期示例
``` text
STARTING
   ↓ success
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

IDLE/BUSY/WAITING/FAILED
   ↓ shutdown
STOPPED
```

team agent 的 State Machine 转移表：
| Current | Event | Guard | Next | Side Effect |
|---|---|---|---|---|
| STARTING | spawn_success | registered | IDLE | emit started |
| IDLE | task_claimed | task valid | BUSY | execute task |
| BUSY | dependency_wait | dependency exists | WAITING | create_task, update_task |
| WAITING | dependency_resolved | — | BUSY | resume |
| BUSY | task_finished | — | IDLE | publish result |
| * | shutdown | can_stop | STOPPED | unregister |
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
