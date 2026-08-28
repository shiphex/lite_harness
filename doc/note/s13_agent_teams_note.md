# Agent Teams

Agent Teams 是 `AgentRuntime` 之上的轻量协作平面，用于让一个 lead 和多个持久
teammate 在同一 session 中完成只读研究、分析和评审。

## 1. 核心结构

```text
TeamCoordinator
├── MessageBus
├── team-scoped TaskStore
└── TeammateWorker
    └── AgentRuntime → run_turn() → query_loop()
```

- Coordinator 管理 roster、消息路由和 Worker 生命周期。
- MessageBus 为每个成员维护一条进程内 FIFO mailbox。
- Worker 复用普通 Runtime，不实现新的 Agent Loop。
- teammate 有独立 history，与 lead 共享 session_id，但使用不同 agent_id。

## 2. 协作方式

lead 使用 `spawn_teammate` 创建成员，成员通过 task 工具显式认领和完成共享任务。
lead 与 teammate、teammate 与 teammate 都可使用 `send_message` 通信；每轮 Worker 的
最终结果统一进入 lead mailbox。lead 使用 `wait_teammates` 声明挂起，由外层
`SessionDriver` 阻塞等待 Queue，并在收齐结果或超时后注入一次 team notification 恢复
推理；`read_messages` 仅用于非阻塞诊断。

当前 MVP 不实现 causal identity、自动认领、自组织循环或持久 mailbox。详细边界见
[Agent Teams 架构文档](../architecture/agent_teams.md)。

