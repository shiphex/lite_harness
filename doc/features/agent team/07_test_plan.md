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

# 2. State Machine Tests
- [ ] STATE-01 STARTING → IDLE allowed
- [ ] STATE-02 IDLE → BUSY allowed
- [ ] STATE-03 IDLE --shutdown--> STOPPED allowed
- [ ] STATE-04 STOPPED → BUSY forbidden
- [ ] STATE-05 STOPPED --task_claimed--> BUSY forbidden


# 3. Failure Tests
- [ ] F-SPAWN-01 → test_spawn_runtime_failure_rolls_back
- [ ] F-SPAWN-02 → test_register_failure_destroys_runtime
- [ ] F-MSG-01 → test_send_to_unknown_member_rejected


# 4. 测试项目

# 4.1 架构测试
- [ ] ARCH-01:
team/registry.py 不允许 import AgentRuntimeFactory

- [ ] ARCH-02:
TeamAgent communication 必须经过 MailboxHandle / MessageBus boundary，
禁止直接访问其他 Agent 或 mailbox storage。

- [ ] ARCH-03:
Agent creation 入口必须经过 LifecycleManager

- [ ] ARCH-04:
全部 TeamAgent 使用 AgentRuntime / query_loop 执行任务

# 4.2 成功标准
`doc\features\agent team\01_problem.md` 中的 `# 4. Success Criteria`



# 5. Traceability Matrix
|state| Requirement | Architecture | Contract | Failure | ADR | Test | Task |
|---|---|---|---|---|---|---|---|
| [ ] | SC-01 spawn | architecture 2.4 | contract 2.4 | F-SPAWN-01/02 | - | - | - |
| [ ] | SC-02 统一 AgentRuntime / query_loop | architecture 1.1/2.2 | AgentRuntime existing contract（如果不在 Agent Team 文档，可写 existing runtime） | - | - | ARCH-04 | - |
| [ ] | SC-03 messaging | architecture 2.3 | contract 2.3 | F-MSG-01 | ADR-004/006 | - | - |
| [ ] | SC-04 lifecycle entry | architecture 2.4 | contract 2.4 | F-STOP-01 | ADR-005 | ARCH-03 | - |
| [ ] | SC-05 no cross-module state mutation | architecture 2.3 | contract 2.3 |  F-MSG-01/02 | ADR-004 | ARCH-02/F-MSG-01 | - |

