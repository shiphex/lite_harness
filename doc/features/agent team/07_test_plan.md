# 1. 测试框架及策略
- pytest
- architecture/import boundary test
- contract test

Test Strategy：
``` text
Unit / contract / state tests:
    no real LLM

Integration:
    FakeAgentRuntime / FakeLLM

E2E smoke:
    optional real model
```

## 1.1 检查项状态语义

- `[ ]`：测试尚未实现，或尚未通过对应阶段的 Human Review。
- `[√]`：已有自动测试覆盖，并在最近一次已接受的阶段验证中通过。
- 已勾选项目自动成为后续 Phase 的回归测试；Phase 2～5 必须持续保持通过，不重复取消勾选。
- 后续实现导致已勾选测试失败时，当前 Phase 不得完成；应修复回归，或通过 Design Change 流程更新已接受的 Contract、测试及其状态。
- 单项勾选不表示 MVP 最终完成；Phase 6 负责全量集成验证，最终完成状态以 Traceability Matrix 与 Success Criteria 为准。

# 2. State Machine Tests
- [√] STATE-01 STARTING → IDLE allowed
- [√] STATE-02 IDLE → BUSY allowed
- [√] STATE-03 IDLE --shutdown--> STOPPED allowed
- [√] STATE-04 STOPPED → BUSY forbidden，拒绝后仍为 STOPPED
- [√] STATE-05 STOPPED --task_claimed--> BUSY forbidden
- [√] STATE-06 正常 shutdown 后 `MemberRegistry.get(agent_id)` 仍返回 STOPPED member record
- [√] STATE-07 fatal runtime error 后 `MemberRegistry.get(agent_id)` 仍返回 FAILED member record


# 3. Failure Tests
- [ ] F-SPAWN-01 → runtime creation failure returns `SpawnError` and leaves no member / lifecycle-owned TeamAgent
- [ ] F-SPAWN-02 → wrapper、register、publication 或 commit failure reverse-cleans ownership；STARTING record uses `SPAWN_ROLLBACK`
- [ ] F-MSG-01 → test_send_to_unknown_member_rejected
- [√] F-STATE-01 → test_invalid_member_transition_rejected_without_state_change


# 4. 测试项目

# 4.1 架构测试
- [√] ARCH-01:
team/registry.py 不允许 import RuntimeFactory

- [ ] ARCH-02:
TeamAgent communication 必须经过 MailboxHandle / MessageBus boundary，
禁止直接访问其他 Agent 或 mailbox storage。

- [ ] ARCH-03:
TeamAgent AgentRuntime creation 入口必须经过 LifecycleManager；Coordinator、TeamAgent 与 team tool 不得调用 RuntimeFactory

- [ ] ARCH-04:
全部 TeamAgent 使用既有 AgentRuntime；`TeamAgent.run(prompt)` 默认进入既有 `query_loop`

- [√] ARCH-05:
TeamRuntime 是独立的 team composition root，不并入 AgentRuntime；team-scoped shared services 由 TeamRuntime 组装并持有。

- [√] ARCH-06:
Team task 集成必须复用现有 task_system 的 TaskStore / task behavior，不得定义第二套 task model 或引入 Scheduler。

# 4.2 Contract / Isolation 测试
- [√] STORE-01 两个 TeamRuntime 使用不同 TaskStore，写入与读取互不污染
- [√] STORE-02 未显式注入 store 的现有工具路径继续使用全局 `TASKS`，原有行为保持兼容
- [√] REGISTRY-01 所有 MemberState transition 均经过 MemberRegistry 的受控入口
- [√] REGISTRY-02 `unregister` 仅可用于 spawn 发布前 rollback 或 TeamRuntime 最终释放
- [ ] SPAWN-01 Master tool → TeamCoordinator → LifecycleManager → RuntimeFactory → MemberRegistry 的整链 fake-runtime 测试返回 IDLE member
- [ ] MASTER-TOOL-01 `spawn_teammate` 只通过 per-instance binding 暴露给 Master，不进入通用 / Subagent / TeamAgent tool set

# 4.3 成功标准
`doc\features\agent team\01_problem.md` 中的 `# 4. Success Criteria`



# 5. Traceability Matrix
|state| Requirement | Architecture | Contract | Failure | ADR | Test | Task |
|---|---|---|---|---|---|---|---|
| [ ] | SC-01 spawn | architecture 1.1/2.1/2.4/2.5 | contract 2.4/2.5/3.1/3.3 | F-SPAWN-01/02 | ADR-001/002/007/008/010 | STATE-01/REGISTRY-02/SPAWN-01/MASTER-TOOL-01 | TASK-03 |
| [ ] | SC-02 统一 AgentRuntime / query_loop | architecture 1.1/2.2 | contract 2.6 | - | ADR-007/009 | ARCH-04 | TASK-03 |
| [ ] | SC-03 messaging | architecture 2.3 | contract 2.3 | F-MSG-01 | ADR-004/006 | - | - |
| [ ] | SC-04 lifecycle entry | architecture 2.4/2.5 | contract 2.4/2.5 | F-SPAWN-01/02、F-STOP-01/F-STATE-01 | ADR-002/005/010 | STATE-03/04/06/07、ARCH-03、REGISTRY-01/02 | TASK-03 / TASK-06 |
| [ ] | SC-05 no cross-module state mutation | architecture 2.3/2.5 | contract 2.2/2.3/2.5 | F-MSG-01/02、F-STATE-01 | ADR-002/003/004 | ARCH-02/06、STORE-01/02、REGISTRY-01 | - |

