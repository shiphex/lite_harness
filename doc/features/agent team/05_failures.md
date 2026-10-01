# 1. 全局 Failure Policy
- 不允许 silent failure
- domain failure 使用 typed error/result
- partial construction 必须 rollback
- shutdown/teardown 应幂等
- teardown 尽量 best-effort cleanup，并汇总失败
- 不在底层无限 retry
- fatal runtime failure 必须有可观察终态
- MemberRegistry 必须拒绝非法 MemberState transition，且拒绝后保持原状态不变
- STOPPED / FAILED member record 必须保留到 TeamRuntime 最终释放
- Phase-2 spawn rollback 保证逻辑资源 / ownership cleanup；当前不承诺删除 RuntimeFactory 已创建的 filesystem diagnostic artifacts
- 正常停止与正常 `q/exit` 不得使原 owner 的未完成任务失去续跑入口；无法安全停止时保留 TeamRuntime 并报告失败


# 2. 具体 Failure Policy
| ID | Failure | Detect | Recovery owner | Recovery Action | Result/Test |
|---|---|---|---|---|---|
| F-SPAWN-01 | runtime create failed | LifecycleManager | LifecycleManager | 返回 `SpawnError`；释放已取得的逻辑 ownership | no member / no lifecycle-owned worker |
| F-SPAWN-02 | wrapper、register、publication 或 IDLE commit failed | LifecycleManager | LifecycleManager | 逆序释放 wrapper/runtime reference；STARTING record 使用 `SPAWN_ROLLBACK` unregister | no member / no lifecycle-owned worker |
| F-MSG-01 | target missing | MessageBus | sender | reject with `MessageTargetNotFoundError` | no enqueue |
| F-MSG-02 | mailbox full | MessageBus | MessageBus | reject with `MailboxFullError` | no silent loss / original queue unchanged |
| F-MSG-03 | sender missing or sender/target STARTING、STOPPED、FAILED | MessageBus | sender | reject with `MessageUnavailableError` | no enqueue / no state change |
| F-MSG-04 | empty、non-string or over 16,384-character content | MessageBus | sender | reject with `InvalidMessageError` | no enqueue |
| F-TASK-01 | task already claimed | TaskStore | caller | conflict | retry/read |
| F-TASK-02 | 领取成功但成员转 BUSY 失败 | TeamCoordinator | Master | 保留 `in_progress` 与原 owner，返回实际 task/member 状态；同一 owner 用 `resume_team_task` 重试转换 | 不虚报执行；不自动退回 pending |
| F-TASK-03 | 执行异常或一轮结束未完成 | TeamCoordinator | Master | 保留 `in_progress` / BUSY；同一 owner 显式续跑 | 可观察错误或未完成结果 |
| F-TASK-04 | 任务完成但成员转 IDLE 失败 | TeamAgent / MemberRegistry | Master | 保留 completed 任务事实和 BUSY 成员；`resume_team_task` 只重试 `TASK_FINISHED` | 不重复执行或重复完成 |
| F-TASK-05 | 非 owner、跨团队成员或同成员重入 | TeamCoordinator / TeamAgent tool | caller | 明确拒绝；不改变目标任务或成员状态 | typed conflict / error |
| F-STATE-01 | invalid member state transition | MemberRegistry | caller | reject；保持原状态 | typed error/result |
| F-STOP-01 | 活动同步 turn 无法停止 | LifecycleManager | Master / Coordinator | 返回 `StopBusyError`；不强制中断、不改变 member/task 或 wrapper ownership；本轮结束后重试 | 不虚报 STOPPED；仍可续跑 |
| F-STOP-02 | 原 owner 有 `in_progress` 任务或完成后的成员收尾未恢复 | LifecycleManager / Coordinator | Master | 拒绝正常停止并保留 Registry；可运行的原 owner 显式续跑/修复，FAILED owner 的任务按 F-STOP-05 交接给新成员后重试 | 不留下不可续跑任务 |
| F-STOP-03 | teardown 中有成员停止或清理失败 | Coordinator / TeamRuntime | Master | 继续处理其他成员，汇总逐成员失败；保留 TeamRuntime 与终态记录以供重试，正常 `q/exit` 拒绝退出 | 不提前报告最终释放 |
| F-STOP-04 | 明确不可恢复的 runtime 故障 | LifecycleManager | Master / runtime supervisor | 报告 `FATAL_RUNTIME_ERROR`，保留 FAILED record、错误摘要与任务事实；普通执行异常仍走 F-TASK-03。若仍有 `in_progress` 任务，正常 teardown 拒绝最终释放 | fatal 可观察，不伪造可恢复执行或安全退出 |
| F-STOP-05 | FAILED 成员任务交接失败 | TeamCoordinator / TaskStore / LifecycleManager | Master | spawn 失败保留原任务；交接前失败停止新建空闲成员；交接后状态转换或执行失败保留新 owner 与可续跑成员，逐项重试或再次显式恢复 | 不丢 owner / 交接记录；现有 IDLE 成员不受影响 |

F-SPAWN-01 / F-SPAWN-02 的 “no leaked worker” 指 LifecycleManager 不再保留可达的 TeamAgent wrapper / AgentRuntime。由于当前 AgentRuntime 没有 `destroy()` / `close()` contract，失败前由 RuntimeFactory 创建的 runtime diagnostic directories 可以保留，不视为 Phase-2 rollback failure。

Phase 3 的 bus 锁只保证单次队列操作原子。Phase 5 已接受的设计要求把消息检查/队列操作与 shutdown / fatal transition 排序：终态转换后的收发明确拒绝，已接受消息到 TeamRuntime 最终释放前不静默丢弃。无后台 worker 或 AgentRuntime 强制关闭契约，不以强制清理代替 F-STOP-01 的可观察拒绝。


# 3. 必然面对的 P0 failures
- runtime crashes after registration
- duplicate member id
- invalid state transition
- task not found
- dependency invalid/cycle（若已有 task_system 负责，可引用）
- message to STOPPED member
- partial teardown failure
- shutdown called twice
- teardown called twice
- TeamAgent runtime crashes while BUSY
