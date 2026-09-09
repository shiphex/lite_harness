# 1. 代码目录
``` shell
team/
    coordinator.py
    lifecycle.py
    registry.py
    messaging.py
    tasks.py
    contracts.py
```

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

TaskStore 不应存在的函数：
- Agent Team 不引入新的 Task state model


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
- services 在整个 team 生命周期内共享



