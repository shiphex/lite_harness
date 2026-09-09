# 0. Terminology / Glossary
``` text
MasterAgent
    team 中负责协调的主 agent。

TeamAgent
    lead 创建的 team member。

AgentRuntime
    执行单个 agent query_loop 的运行环境。

TeamRuntime
    一支 team 的运行环境与共享服务集合。

TeamCoordinator
    编排 team-level use cases。

MemberRegistry
    保存 team member metadata。

MessageBus
    负责 team message routing。

TaskStore
    保存共享 task state。
```

# 1. 架构设计

## 1.1 team 架构设计

``` text
                     TeamRuntime
   ┌──────────────────────────────────────────────────┐
   │                                                  │
   │         composition root / team context          │
   │                       │                          │
   |       ┌───────────────┼─────────────────┐        │
   |       ▼               ▼                 ▼        │
   | TeamCoordinator   MemberRegistry    MessageBus   │
   |       │                                          │
   |       ├──────────────→ TaskStore                 │
   |       │                                          │
   |       └──────────────→ LifecycleManager          │
   └──────────────────────────────────────────────────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
      MasterAgent       TeamAgent A     TeamAgent B
      AgentRuntime      AgentRuntime    AgentRuntime
            │              │              │
            └──────────────┼──────────────┘
                           ▼
                       run_turn()
                           │
                           ▼
                       query_loop()

```

# 2. 模块边界设计

## 2.1 TeamCoordinator 边界设计
```
                 TeamRuntime
       composition root / team context
                      │
      ┌───────────────┼─────────────────┐
      ▼               ▼                 ▼
TeamCoordinator MemberRegistry      MessageBus
      │
      ├──────────────→ TaskStore
      │
      └──────────────→ LifecycleManager
```
- TeamRuntime = 一支 team 的运行环境和依赖集合
- Coordinator = orchestration / use-case 层，负责协调，不负责实现所有东西
- TaskStore：共享任务存储，用于存储和管理团队任务(create_task、claim_task、update_task、get_task、list_tasks)，底层基于已有 task_system
- LifecycleManager：负责“怎么创建/停止 worker”
- MemberRegistry：负责“现在有哪些 worker”
- MessageBus：负责各个团队成员之间的消息传递

## 2.2 Agent 边界设计
一个 Agent 拥有：
``` text
Agent
|
+ Runtime
|  |
|  + Memory
|  |
|  + Identity
|
+ MailboxHandle
```
- Memory 属于 AgentRuntime。Agent Team 不引入新的记忆模型。
- Identity 属于 AgentRuntime。由 AgentRuntime 初始化(session_id、agent_name、agent_id)。


## 2.3 Mailbox 边界设计
关于 mailbox 与 MailboxHandle 的关系：
``` text
MessageBus
    owns:
        MessageBus.route / enqueue / mailbox[agent_id] ownership
Agent
    owns:
        MailboxHandle:
            MailboxHandle.send()
            MailboxHandle.receive()
```
Agent “拥有 mailbox 能力”，但不拥有 mailbox 数据结构本身。

## 2.4 LifecycleManager 边界设计

LifecycleManager 什么时候销毁 TeamAgent？
- A. MasterAgent 显式 shutdown
- B. Team 完成后统一 teardown
- C. fatal error

关于 Team 中 Agent 状态及生命周期的管理分工： 
``` text
LifecycleManager
    管 worker 生命周期

MemberRegistry
    管 team-visible member metadata
    包括当前 MemberState 
        (具体状态及 transition 见 03_runtime.md #1.2)

TeamAgent
    通过明确接口 report_state(...)
```

## 2.5 MemberRegistry 边界设计

责任:
- register member
- unregister member
- query members
- maintain member metadata
- owns MemberState

不能负责:
- spawn AgentRuntime
- send message
- assign task
- call LLM


## 2.6 边界设计列表
| Module | Responsibilities | Must NOT |
|---|---|---|
| TeamCoordinator | 编排 use case、协调 shared services | 保存 mailbox、直接构造 runtime、调用 LLM |
| LifecycleManager | spawn/shutdown/teardown/cleanup | 任务调度、消息路由、业务推理 |
| MemberRegistry | member metadata/state | spawn、message、task、LLM |
| MessageBus | mailbox ownership、routing | 调用 AgentRuntime、任务调度、Agent lifecycle |
| TaskStore | task CRUD/state/dependency | 选择“最合适 Agent”、创建 Agent、发消息 |


# 3. mini-ATAM / Architecture Evaluation
| Driver | Tactic | Sensitivity / Trade-off | Risk | Disposition | Evidence |
|---|---|---|---|---|---|
| 可维护性 | 分离 Registry/Lifecycle | 组件数增加 | Low | Accept | ARCH tests |
| 隔离性 | MailboxHandle | MessageBus 成共享关键点 | Medium | Mitigate | contract + F-MSG |
| 可扩展性 | 统一 AgentRuntime | runtime contract 成敏感点 | Medium | Mitigate | SC/runtime test |
| 简单性 | 暂无 Scheduler | 无自动调度 | Low | Accept | ADR-003 |
| 生命周期 | explicit teardown | idle worker 存活 | Low | Accept | ADR-005 |