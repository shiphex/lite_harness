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
| IDLE/BUSY/WAITING | shutdown | can_stop（无活动 turn、无原 owner 未完成任务、无待恢复的完成收尾） | STOPPED | record terminal state / emit stopped |
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

Phase 5 的 `can_stop` 在 LifecycleManager / Coordinator 用例边界校验，不由 Registry 猜测 TaskStore 状态。活动同步 turn 返回 `StopBusyError`；仍有原 owner `in_progress` 任务，或任务已完成但成员收尾转换未恢复时，拒绝正常停止并保留 wrapper 和成员状态，Master 先用原 owner 显式续跑或修复后重试。正常 `q/exit` 的 teardown 如有此类失败，报告结果并保持会话，不留下因正常停止而不可续跑的任务。普通执行异常仍按 F-TASK-03 / 04 恢复，不自动转 FAILED；明确不可恢复的 runtime 故障由 LifecycleManager 报告 fatal 并保留 FAILED record。

若 FAILED 成员仍有 `in_progress` 任务，Master 可调用 `recover_failed_team_task(task_id)`：校验原 owner 为 FAILED → 新建独立 TeamAgent → 保持任务 ID / 状态并持久记录 owner 交接 → 新成员 IDLE→BUSY → 同步运行一轮。原 FAILED 成员不复活，既有 IDLE 成员不接手。交接前失败时任务仍属于原 owner；交接后状态转换或执行失败时，新 owner 保留 `in_progress` 任务并可显式续跑；新成员再次 FAILED 时可再次恢复。


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
    ↓ TeamCoordinator: claim → Registry BUSY → TeamAgent.run(task prompt)
TeamAgent
    ↓ complete_team_task: TaskStore complete → Registry IDLE
```

以上 Team 路径操作 TeamRuntime 持有的 team-scoped TaskStore。现有 task-system operation 通过显式 store 注入复用；未显式注入时仍保留绑定全局 `TASKS` 的既有工具路径。具体采用函数参数、bound handler 或薄 adapter，延后到对应 Phase 决定。

Phase 4 中 Master 可先在 team store 创建任务，再从看板查看并指定本团队 IDLE 成员的实际 `agent_id` 分配。分配同步等待一次 `TeamAgent.run(prompt)`；任务指令直接作为 prompt，不写 mailbox。任务执行期间，TeamAgent 可使用其团队任务工具和现有工作区工具。

执行异常或一轮结束仍未完成时，任务保持 `in_progress`、原 owner 不变，成员保持 BUSY；Master 仅可对同一 owner 显式续跑。若领取已持久化但 BUSY 转换失败，续跑先重试该转换；若任务已完成但 IDLE 转换失败，续跑只重试收尾转换，不再运行任务。不可恢复的状态冲突明确返回实际状态和错误；不自动退回 `pending`。

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

Phase 3 的消息收发是同步、非阻塞操作：每个 mailbox 是最多 100 条消息的 FIFO 队列，空队列 receive 返回 `None`，满队列 send 立即拒绝且不丢失旧消息。单条 content 最多 16,384 字符。Bus 只接受本 TeamRuntime Registry 中处于 IDLE / BUSY / WAITING 的 sender 与 target；STARTING / STOPPED / FAILED 成员不可收发。收发不触发 TeamAgent `run()`、模型执行或 MemberState transition；ADR-006 的 one-message-one-turn 执行驱动留待后续阶段。


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

Phase 5 的 teardown 对每个成员尽力停止并汇总失败；有失败则保留 TeamRuntime、未完成任务和可查询终态以供重试。全部成员安全停止且逻辑 ownership 清理后，才以 `TEAM_RELEASE` 移除 Registry record、释放内存 mailbox；session TaskStore 文件不删除。重复停止与重复 teardown 不产生第二次副作用。消息收发与 shutdown / fatal transition 的共同顺序边界保证转换后的收发被拒绝。
