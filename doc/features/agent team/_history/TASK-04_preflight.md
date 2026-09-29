# TASK-04 Preflight Brief

Status: Archived / Non-authoritative

Task: TASK-04 Messaging Vertical Slice

Baseline: `f8c76c4611e582e99245c9638f3dc5206db3e868`

Outcome: 技术预检完成；DD-01～DD-04 提交设计审阅，裁决见 [`../Human_Review.md`](../Human_Review.md)

Source of Truth: `../01_problem.md`～`../08_tasks.md`；本报告只记录预检证据与提案

## Preflight Verdict

**技术上可行，设计裁决与传播完成前不进入实现。** Phase 3 限于 MailboxHandle / MessageBus 的同步收发；消息不触发 `TeamAgent.run()`、后台执行或 MemberState 转换。

## Baseline 与代码事实

- 目标分支 `feature/team`；HEAD 为上述 baseline。工作区原有未提交改动位于 `../01_problem.md`、`../07_test_plan.md`、`../08_tasks.md` 和 `TASK-03_completion-review.md`，预检未修改代码。
- 基线命令 `uv run python -m pytest -q`：`259 passed in 2.36s`；`git diff --check` exit 0，仅有 LF→CRLF working-copy 提示。
- `MessageBus` 只有 `_mailboxes` shell，没有 send、receive 或 MailboxHandle：`f8c76c4/team/messaging.py:4`～`:8`。
- `TeamRuntime` 已分别组装 Registry、MessageBus、LifecycleManager，但 bus 尚未连接 Registry 或 LifecycleManager：`f8c76c4/team/runtime.py:27`～`:35`。
- LifecycleManager 是 wrapper owner，spawn 目前只以 `runtime=` 构造 TeamAgent；可达 wrapper 存在 `_agents`，没有公开的只读查询入口：`f8c76c4/team/lifecycle.py:57`、`:78`、`:85`。
- TeamAgent 目前只持有 AgentRuntime 和 query loop：`f8c76c4/team/agent.py:20`～`:33`。TeamAgent policy 只包含 `read_file`、`glob`、`load_skill`：`f8c76c4/team/lifecycle.py:26`、`:121`～`:130`。
- MemberRegistry 已提供受控 `get()` / `transition()` 与 STOPPED / FAILED 记录：`f8c76c4/team/registry.py:117`、`:138`。现有工具执行器只执行 allowed tool set：`f8c76c4/tools/tool_handler.py:18`～`:29`。

## 拟修改模块

- `team/messaging.py`：TeamMessage、绑定身份的 MailboxHandle、team-scoped MessageBus 队列及 typed messaging errors。
- `team/runtime.py`、`team/lifecycle.py`、`team/agent.py`、`team/contracts.py`：同一个 Registry / Bus 的依赖传递、wrapper 的 handle、只读 wrapper 查询及错误类型；不更改 RuntimeFactory、query_loop 或 Master/Subagent 通用工具。
- `tests/team/*`：消息 contract、失败、FIFO、并发原子性、跨 team 隔离、spawn 绑定与 ARCH-02；保留已接受的全部回归。
- 设计裁决接受后，先同步 `02_architecture.md`～`08_tasks.md` 中相应 contract、failure、test 与任务状态，再进入代码实现。

## Design Deltas 待审阅

### DD-01：消息格式、API 与身份绑定

当前 `04_contracts.md` 只有 `send(...)` / `receive(...)`，没有消息格式、空队列结果或 sender 身份规则。

**建议裁决：**

- 最小不可变 `TeamMessage(sender_id: str, target_id: str, content: str)`；成员 ID 使用 RuntimeFactory 实际 `agent_id`，content 是非空文本。Phase 3 不加入消息 ID、时间戳或会话协议。
- `MailboxHandle.send(target_id: str, content: str) -> None` 和 `receive() -> TeamMessage | None`；`None` 表示当前无消息，调用非阻塞。
- Handle 由 LifecycleManager 为当前 TeamAgent 绑定，sender_id 不由 send 调用者传入或更改。MessageBus 提供 Contract 已列出的 send / receive / `_enqueue`，在服务端验证成员身份；TeamAgent 只能通过自身 handle 使用这些操作。

### DD-02：容量、并发与失败

`05_failures.md` 要求 mailbox 满时 reject/backpressure、不得 silent loss，但没有容量或原子性规则。

**建议裁决：**

- 每个 mailbox 使用 FIFO 队列，默认最多 100 条；构造 MessageBus 时可传正整数容量供确定性测试使用，不新增全局配置。
- send / receive 在 bus 内同步加锁，目标验证与入队、出队分别为原子操作；空队列返回 `None`，满队列立即拒绝，不阻塞、不重试、原队列不变。
- 使用 `MessageTargetNotFoundError`、`MailboxFullError`、`MessageUnavailableError`、`InvalidMessageError` 等 `TeamError` 子类表达可预期失败。Phase 3 不承诺磁盘持久化；极大消息的字节容量限制留待未来暴露模型工具时裁决。

### DD-03：状态规则与 team 隔离

`05_failures.md` 将发往 STOPPED member 列为 P0，却未指定行为；MessageBus 当前没有 Registry 依赖。

**建议裁决：**

- MessageBus 只使用所属 TeamRuntime 的 MemberRegistry 验证 sender / target，不查询全局成员；不同 TeamRuntime 不共享 mailbox。不存在的 target 触发 F-MSG-01，已 STOPPED / FAILED 或尚在 STARTING 的成员触发 `MessageUnavailableError`，不入队。
- IDLE / BUSY / WAITING 成员可收发；已 STOPPED / FAILED / STARTING 的 sender 同样被拒绝。receive 从空队列返回 `None`，不改变 MemberState。
- 状态只在每次 bus 操作入口检查；并发 shutdown 与消息投递之间的跨模块线性化留给 Phase 5 的 shutdown 设计，不把 Registry 锁或生命周期行为移入 MessageBus。

### DD-04：spawn 接缝与工具暴露

TeamAgent 当前没有 MailboxHandle；在 RuntimeFactory.create 前还没有实际 agent_id。Phase 3 又明确不让消息触发执行。

**建议裁决：**

- RuntimeFactory 返回实际 agent_id 后，LifecycleManager 创建绑定该 ID 的 handle，并在创建 wrapper 时传入；成功发布后每个 TeamAgent 都持有一个 handle。MessageBus 按需创建 mailbox，不在 spawn 时预先注册队列，因此 commit 前 rollback 不留下 mailbox。
- TeamAgent 构造器在 Phase 3 要求 handle；相应调整 Phase-2 wrapper 测试与 `04_contracts.md` §2.6。LifecycleManager 提供只读 `get_agent(agent_id)` 供集成测试与后续编排取回其持有的 wrapper，不转移 ownership。
- Phase 3 只暴露 wrapper 的 handle API，不新增模型可调用的消息工具；后续执行触发阶段再裁决工具能力、事件路由与 one-message-one-turn 的实际驱动方式。

## 验证门槛与范围检查

- 为 F-MSG-01 / F-MSG-02、STOPPED / FAILED / STARTING 目标、无效 sender、空队列、FIFO、满队列不丢失、跨 TeamRuntime 隔离与并发发送增加确定性测试；ARCH-02 检查 TeamAgent 不直接访问 MessageBus storage 或其他 Agent。
- 整链测试从两个已发布 TeamAgent 的 handle 完成 send / receive；消息操作不调用 `run()`、模型或 Registry.transition()，Phase 3 与 SC-03 仅在实现及完成审阅后勾选。
- 已勾选的 spawn / registry / store 测试保持通过；不实现 task collaboration、shutdown、teardown、Scheduler、worktree 或真实模型 smoke。

## 结论

**Blocked pending design review and authoritative propagation.** 上述四项是具体机制裁决，不改变既有 team ownership、被动 spawn 或阶段范围。审阅结论写入 `../Human_Review.md`；实施者需先据已接受裁决更新 authoritative documents，再开始代码。
