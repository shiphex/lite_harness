# 1. 当前遇到的问题

## 1.1 背景
随着 AI coding agent 的普及，开发者可以快速生成大量代码。
但是缺少明确架构约束时，agent 生成代码容易出现：

- 模块职责模糊
- 重复实现
- 难以理解
- 难以持续演进

## 1.2 当前状态
分支(feature/agent_teams)并非本人编写，而是codex自行编写，存在问题：
- 该分支的代码“发散”、臃肿、缺乏边界定义
- 难以持续演进    
- 无相关文档，难以理解代码

故重新开发 feature/team 分支，致力于：
1. 开发者(我)希望通过规范化的人与 agent 协作开发流程重新开发本分支，重构 agent team 相关代码，以提高代码的质量和可维护性。
2. 通过与 agent 协作开发，开发者(我)希望能够学习到更多关于 agent 开发的知识，同时也能提高自己的开发技能。


# 2. Goal

1. Product Goal
以规范化的流程重新开发 feature/team 分支(可适当参考 feature/agent_teams 分支的代码)

2. Learning Goal
学习 agent team 相关知识、实现 agent team 功能、掌握规范化的人与 agent 协作开发 Spec-Driven Development 流程。

3. Process Goal
建立一套可复用的人-Agent Spec-Driven Development 流程。

## 2.1 阶段开发目标：

Architecture：
- 引入 TeamRuntime 作为 team composition root / context；
- 引入 TeamCoordinator 编排 team-level use cases；
- LifecycleManager 管理 TeamAgent 生命周期；
- MemberRegistry 管理 team member metadata/state；
- MessageBus 负责 team communication；
- TaskStore 复用已有 task_system 维护共享 task state；
- TeamAgent 复用统一 AgentRuntime / query_loop。


Capability：
- MasterAgent 可以创建多个 TeamAgent
- TeamAgent 可以独立执行任务
- TeamAgent 可以使用 MessageBus 互相通信
- TeamAgent 可以共享任务状态
- 每个 TeamAgent 都拥有独立的 MailboxHandle，通过 MessageBus 管理的 mailbox 发送和接收消息。
- MasterAgent 可以从看板中检索任务，再分配给 Teamagent 执行
- TeamAgent 具有可观察的生命周期/运行状态
- MasterAgent 可实现 explicit shutdown、team teardown


# 3. Non-goal

当前不做的功能：
1. 暂时不实现 worktree、workspace 功能。
2. Teamagent 空闲时自行从看板中检索任务并执行。
3. shutdown 中的 idle timeout、token/cost eviction 策略。


# 4. Success Criteria
- [ ] SC-01 MasterAgent 可以创建至少一个 TeamAgent；
- [ ] SC-02 TeamAgent 使用现有统一 AgentRuntime / query_loop 执行任务；
- [ ] SC-03 TeamAgent 之间只能通过明确的 team communication contract 通信；
- [ ] SC-04 TeamAgent 的创建、销毁必须经过统一生命周期入口；
- [ ] SC-05 task、member、message 不允许跨模块直接修改内部状态；
- [ ] SC-06 happy path 和主要 failure path 有自动测试覆盖；
- [ ] SC-07 实现不引入 `#3 Non-goal` 中定义的能力。


