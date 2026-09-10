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


# 2. 具体 Failure Policy
| ID | Failure | Detect | Recovery owner | Recovery Action | Result/Test |
|---|---|---|---|---|---|
| F-SPAWN-01 | runtime create failed | LifecycleManager | LifecycleManager | rollback | no member |
| F-SPAWN-02 | register failed | LifecycleManager | LifecycleManager | destroy runtime；若存在尚未发布的 record，则 rollback / unregister | no leaked worker / no member |
| F-MSG-01 | target missing | MessageBus | sender | reject | typed error |
| F-MSG-02 | mailbox full | MessageBus | MessageBus | reject/backpressure | no silent loss |
| F-TASK-01 | task already claimed | TaskStore | caller | conflict | retry/read |
| F-STATE-01 | invalid member state transition | MemberRegistry | caller | reject；保持原状态 | typed error/result |
| F-STOP-01 | worker won't stop | LifecycleManager | Coordinator | force cleanup policy；通过 MemberRegistry 记录终态 | queryable FAILED/STOPPED record |


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
