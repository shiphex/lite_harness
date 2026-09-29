# TASK-04 Design Review

Status: Accepted Review (user-delegated technical review)

Task: TASK-04 Messaging Vertical Slice

Based on: [_history/TASK-04_preflight.md](_history/TASK-04_preflight.md)

Reviewer: Codex。用户委托执行 preflight 与设计审阅；本文件不冒称用户本人逐项审阅。

Result: DD-01、DD-03 接受；DD-02、DD-04 按下列修改接受。实现仍待 authoritative documents 传播；本次审阅不表示 Phase 3 或 SC-03 已完成。

## 审阅依据

- `08_tasks.md` 要求 TeamAgent 经 MailboxHandle / MessageBus 完成可测试收发，且消息不自动触发 `run()`。
- `02_architecture.md` §2.3、`04_contracts.md` §2.1 / §2.3 与 ADR-004 已确定 bus 拥有 mailbox、Agent 持有窄 handle；F-MSG-01 / F-MSG-02 要求目标不存在与满载失败可观察。
- 基线 `f8c76c4` 的 `team/messaging.py` 仍是空行为 shell；`team/lifecycle.py` 在 RuntimeFactory 返回实际 agent_id 后创建 TeamAgent，当前 policy 仅有三个只读工具。
- `uv run python -m pytest -q` 在 preflight 基线执行：259 passed。该结果只证明现有回归基线，不证明 Phase 3 已实现。

## DD-01：消息 API 与身份绑定 — 接受

- 使用不可变 `TeamMessage(sender_id, target_id, content)`，其中 ID 是实际 `agent_id`，content 为非空文本；Phase 3 不加入消息 ID、时间戳或 conversation session。
- `MailboxHandle.send(target_id, content) -> None`、`receive() -> TeamMessage | None`；空队列返回 `None`，操作为同步非阻塞。
- LifecycleManager 绑定 handle 的 sender_id；调用者不能在 send 参数中指定或更换 sender。TeamAgent 只通过该 handle 收发，MessageBus 保留 `send` / `receive` / `_enqueue` 的服务边界。

## DD-02：容量、失败与并发 — 修改后接受

- 接受每个 mailbox 默认 100 条、构造时可配置正整数容量、FIFO、满载立即抛 typed error 且原队列不变；bus 内锁保护单次 send / receive，不阻塞、不重试。
- 增加 content 长度上限 16,384 个字符，在入队前校验；空白文本、非字符串或超长文本均抛 `InvalidMessageError`。消息条数上限不能限制单条输入的内存占用。
- 使用 `MessageTargetNotFoundError`、`MailboxFullError`、`MessageUnavailableError`、`InvalidMessageError`（均为 `TeamError` 子类）。不承诺持久化或跨进程投递。

## DD-03：成员状态与隔离 — 接受并限定并发承诺

- MessageBus 只查询本 TeamRuntime 的 MemberRegistry；不存在的目标按 F-MSG-01 拒绝。STARTING / STOPPED / FAILED 的 sender 或 target 均以 `MessageUnavailableError` 拒绝；IDLE / BUSY / WAITING 可收发。
- 不同 TeamRuntime 不共享 bus、mailbox 或 member 查询；receive 空队列返回 `None`，收发不调用 `MemberRegistry.transition()`。
- Phase 3 的锁只保证 bus 队列操作原子；与 Phase 5 尚未实现的并发 shutdown **不承诺跨模块线性化**。后续 shutdown 设计必须检查“状态刚被 STOPPED 时正在投递”的竞态。

## DD-04：spawn 接缝与消息工具 — 修改后接受

- 接受 RuntimeFactory 返回实际 agent_id 后由 LifecycleManager 创建并注入 handle，TeamAgent 构造器要求 handle；同步调整既有测试与 `04_contracts.md` §2.6。Bus 按需创建队列，commit 前 rollback 不留下 mailbox。LifecycleManager 可提供只读 `get_agent(agent_id)`，不转移 wrapper ownership。
- Phase 3 需要最小的 TeamAgent 专属 `send_team_message` / `receive_team_message` 工具定义与 handler。否则 query_loop 中的 TeamAgent 无法使用通信能力，Messaging Vertical Slice 只剩宿主对象 API。工具只进入 TeamAgent 的 per-instance policy，不进入 Master 或普通 Subagent 的通用工具集合。
- Handler 依据 `ToolContext.runtime` 取当前 TeamAgent 的已绑定 handle，不接受 sender_id 参数；校验 context runtime 与 LifecycleManager 持有的 wrapper 相同，防止跨实例调用。工具把消息或空队列结果转换为明确的文本 / JSON，捕获并呈现 typed team error。
- 工具调用仅在 TeamAgent 已被其他阶段或测试显式运行时发生；send / receive 本身不启动 `run()`、后台线程、模型调用或 MemberState transition。one-message-one-turn 的执行驱动仍留待后续裁决。

## 传播与实施门槛

1. 将上述裁决传播到 `02_architecture.md`、`03_runtime.md`、`04_contracts.md`、`05_failures.md`、`06_decisions.md`（新增 ADR-011：Phase-3 messaging protocol）、`07_test_plan.md` 与 `08_tasks.md`；保留 ADR-004 的 mailbox ownership 和 ADR-006 的 one-message-one-turn 方向。
2. 测试计划需覆盖正常收发、空队列、FIFO、目标不存在、容量与长度边界、STOPPED / FAILED / STARTING、伪造 sender、跨 team 隔离、TeamAgent-only 工具绑定，以及“不自动执行 / 不改变 MemberState”。
3. 传播完成后 TASK-04 才能进入实现；实现及 Completion Review 接受前，Phase 3、SC-03 和相关新测试继续保持未完成状态。`_history/TASK-04_preflight.md` 保存原始提案，本文件记录本次裁决。
