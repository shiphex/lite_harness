# 1. ADR 必须包含的内容

ADR 需要：
- Status
- Context
- Decision
- Alternatives
- Consequences


# 2. ADR 项目

- [Accepted] ADR-001
TeamRuntime 与 TeamCoordinator 是什么关系？
Decision:
    TeamRuntime 是 composition root；
    TeamCoordinator 是 orchestration layer。

Reason:
    避免 Coordinator 变成 God Object。

Consequence:
    shared service 由 TeamRuntime 持有。


- [Accepted] ADR-002
TeamAgent state 由谁拥有？
Decision:
    MemberRegistry 管理 team member state；

Reason:
    若 Agent 管理 state，管理时不易集中。

Consequence:
    MemberRegistry 管理 team member state


- [Accepted] ADR-003
TaskStore vs TaskScheduler？
Decision:
    TaskStore 管理任务

Reason:
    TaskScheduler 复杂度太高，当前实现过于臃肿。

Consequence:
    TaskStore 管理任务



- [Accepted] ADR-004
Mailbox ownership？
Decision:
    由 MessageBus 管理 mailbox。

Reason:
    若 Agent 管理 mailbox，管理时不易集中。

Consequence:
    MessageBus 管理 mailbox


- [Accepted] ADR-005
TeamAgent shutdown policy？

Context
需要确定 TeamAgent 生命周期结束条件。

Options
A explicit shutdown
B team teardown
C idle timeout
D budget exhaustion

Decision
MVP only A + B.

Consequences
+ 简单、确定性强
+ 容易测试
- 暂时不会自动回收 idle worker

Deferred
idle timeout 留待后续。



- [Accepted] ADR-006
Message semantics:
one-message-one-turn vs conversation session？

Context
需要确定 一条消息 BUSY 然后再 IDLE，一次还是整个聊天期间一直 BUSY。

Options
A one-message-one-turn
B conversation session

Decision
A one-message-one-turn


Consequences
+ 简单、确定性强
+ 容易测试
- 暂时不实现 conversation session


