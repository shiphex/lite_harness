# Agent Teams 协作平面

Agent Teams 让一个 lead 与多个持久 teammate 在同一 session 内协作。它是
`AgentRuntime` 上方的轻量 coordination plane，不引入新的 Runtime 类型或模型循环。

## 1. 架构边界

```text
MasterSession
├── lead AgentRuntime ─────────────┐
└── TeamCoordinator               │
    ├── MessageBus                │
    ├── team-scoped TaskStore     ├── run_turn() → query_loop()
    └── TeammateWorker            │
        └── teammate AgentRuntime ┘
```

- `AgentRuntime` 管理单个 Agent 的策略、状态和运行组件。
- `run_turn()` 管理输入 Hook、history 追加、run 状态重置和 `query_loop()` 调用。
- `TeamCoordinator` 管理 roster、共享任务、消息路由和 Worker 生命周期。
- `MessageBus` 为每个成员维护一条进程内 FIFO `Queue`。
- `TeammateWorker` 只把初始 prompt 和 mailbox 消息转换成 `run_turn()`。

lead、subagent 和 teammate 始终复用同一执行内核。`team/` 按 contract、bus、worker、
coordinator 和 factory 分层，避免把协作协议塞进 Runtime 或 LLM 工具适配器。

## 2. Identity 与 Context

同一 team 内的 Runtime 共享 `session_id`，但拥有不同 `agent_id`：

```text
session_id = abc123
lead.agent_id  = lead-xxxx
alice.agent_id = alice-yyyy
bob.agent_id   = bob-zzzz
```

teammate 使用空 history 创建，不继承 lead 对话。Worker 在 follow-up 之间复用同一个
Runtime，因此成员自己的分析上下文可以持续保留。

teammate name 必须符合 `^[A-Za-z][A-Za-z0-9_-]{0,31}$`。终态成员仍保留在 roster，
所以同一 team 生命周期内不能复用名称。默认最多 3 名活跃 teammate，可通过
`--team_max_members` 调整。

## 3. Task 协作

MasterSession 使用 `.agents/teams/{team_id}/tasks` 下的独立 TaskStore。lead 可以创建任务
和依赖；teammate 通过共享的 `list_tasks、get_task、claim_task、complete_task` 显式
选择并推进工作。`spawn_teammate` 不绑定 task，也不隐式认领任务。

TaskStore 使用单个 `RLock` 保护 create、依赖更新、claim 和 complete 的
read-modify-write 流程。同一个 team 共享一份 store，不同 team 的任务目录相互隔离。

`TeamMember.current_task` 不保存重复状态。Coordinator 生成 roster 快照时，根据
`owner=member.name` 且 `status=in_progress` 的任务动态推导该字段。

## 4. Mailbox 与消息路由

`TeamMessage.kind` 是轻量字符串，MVP 使用以下值：

- `assignment`：spawn 时交给 Worker 的初始 prompt。
- `message`：lead 或 teammate 显式发送的单向消息。
- `result`：Worker 每次 `run_turn()` 结束后的最终文本。
- `shutdown`：用于唤醒并停止 Worker 的内部消息。

`send_message` 支持 lead 与 teammate、teammate 与 teammate 双向通信。peer 消息会触发
接收方的下一次 `run_turn()`；该轮隐式结果仍统一发给 lead。若要回复 peer，模型必须
显式调用 `send_message`，从而避免两个 Worker 自动互发 result。

`read_messages` 是非阻塞 drain：按 FIFO 顺序返回并清空当前 Agent 的 mailbox。
mailbox 只传输消息，不直接操作 Runtime history，也不持久化到磁盘。

## 5. 工具与权限

lead 和 teammate 共用：

- `send_message(recipient, content)`
- `read_messages()`
- `list_team()`

仅 lead 拥有：

- `spawn_teammate(name, role, prompt)`
- `shutdown_teammate(name)`

`spawn_teammate` 的 PreToolUse Hook 始终返回 `ASK`。teammate 使用
`NonInteractiveInteraction`，不能通过非交互 Runtime 绕过审批。

第一版 teammate 仅可使用：

- 项目读取：`read_file、glob、load_skill`。
- 共享任务：`list_tasks、get_task、claim_task、complete_task`。
- 团队通信：`send_message、read_messages、list_team`。

teammate 不提供 shell、文件写入、任务创建、依赖更新、subagent 或 spawn。该边界由
Runtime 的工具定义和 handler allowlist 同时限制，不只依赖 prompt。

## 6. 状态、事件与关闭

成员状态为 `starting、working、idle、stopping、stopped、failed`。协作层发布：

- `team.member.spawned`
- `team.member.status_changed`
- `team.message.sent`
- `team.message.received`
- `team.member.stopped`

lead 与 teammate 共享 `SynchronizedEventSink`，每个事件仍使用实际发送或接收消息的
Runtime metadata。

`shutdown_teammate` 设置停止标记，并发送内部 shutdown 消息唤醒等待中的 Worker。它
不会中断正在执行的 `run_turn()`；当前 run 返回后线程退出。`MasterSession.close()` 会
请求关闭全部 Worker，并在共享的 5 秒截止时间内等待；未及时结束的线程保持 daemon。

## 7. 本阶段明确不实现

以下能力属于后续阶段，不纳入当前 MVP：

- Team Protocol：request/ack graceful shutdown、plan approval、自动 result notification
  或 lead 唤醒、`wait_teammate(s)`。
- Autonomous Team：idle task scan、自动认领和自组织循环。
- Worktree Isolation：并行写代码、task-bound worktree 和独立分支。
- team shared/private memory、持久 roster、持久 mailbox 和远程 transport。

基础协作式 shutdown、结果投递和 task 手动认领仍属于 MVP。第一版定位为项目文件只读
的研究、分析和评审。
