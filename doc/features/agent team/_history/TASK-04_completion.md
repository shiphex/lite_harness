# TASK-04 Completion Report

Status: Archived / Non-authoritative

Task: TASK-04 Messaging Vertical Slice

Baseline: `f8c76c4611e582e99245c9638f3dc5206db3e868`

Outcome: Implementation complete; awaiting Completion Review

Source of Truth: `../01_problem.md`～`../08_tasks.md`

Preflight: [`TASK-04_preflight.md`](TASK-04_preflight.md)

Accepted design review: [`TASK-04_human-review.md`](TASK-04_human-review.md)

## Implemented

- 已将 DD-01～DD-04 传播到 architecture、runtime、contracts、failure policy、ADR-011、test plan 与 current task。
- `MessageBus` 使用所属 TeamRuntime 的 MemberRegistry 验证成员状态，持有按需创建的有界内存 FIFO；每次收发由 bus 锁保护，空队列返回 `None`，满载抛 `MailboxFullError` 且保留原队列。
- `TeamMessage` 为不可变消息，`MailboxHandle` 固定 sender 身份；content 限非空文本、最多 16,384 字符。成员 ID 必须与 Registry 中的实际 ID 完全一致，避免路由进入不可达队列。
- 已为目标不存在、成员不可用、队列满、content 无效建立 `TeamError` 子类。IDLE / BUSY / WAITING 成员可收发；STARTING / STOPPED / FAILED 成员不可收发。
- TeamRuntime 将同一个 bus 交给 LifecycleManager。LifecycleManager 在取得实际 runtime `agent_id` 后绑定 handle 并注入必需该参数的 TeamAgent wrapper；独立构造 LifecycleManager 仍可使用默认 bus，并新增只读查询 `get_agent()`。
- 仅 TeamAgent policy 包含 `send_team_message` / `receive_team_message`。Handler 经 `ToolContext.runtime` 查找 wrapper、验证对象身份并使用其 handle；成功结果为 JSON，typed error 以含异常类型名的工具文本呈现。

## Files Changed

- `team/messaging.py`、`team/messaging_tools.py`、`team/contracts.py`、`team/__init__.py`：消息契约、队列、错误与 TeamAgent 专属工具。
- `team/runtime.py`、`team/lifecycle.py`、`team/agent.py`：bus 组装、handle 绑定与 wrapper 接缝。
- `tests/team/test_messaging.py`、`tests/team/test_messaging_integration.py`、`tests/team/test_lifecycle.py`、`tests/team/test_team_agent.py`：消息 contract、整链、工具、架构边界与构造器回归。
- `../02_architecture.md`～`../08_tasks.md`：传播设计裁决并记录实现状态；本报告作为完成审阅证据。

## Tests

- 实现前 baseline：`uv run python -m pytest -q` → `259 passed`。
- 消息模块和集成测试：`uv run python -m pytest -q tests/team/test_messaging.py tests/team/test_messaging_integration.py` → `34 passed in 1.81s`。
- 最终全量回归：`uv run python -m pytest -q` → `293 passed in 3.10s`。
- `git diff --check` exit 0；仅有 Git 的 LF→CRLF working-copy 提示，没有 whitespace error。
- 测试先于核心实现失败，再在实现后通过；审阅发现非规范 ID 可进入不可达队列及工具错误丢失类型名，已补回归测试并修复，审阅者对这两处修复复核通过。

## Boundary Checks

- 测试覆盖正常收发、空队列、FIFO、默认 100 条容量与自定义容量、16,384 字符边界、各成员状态、缺失目标、非规范及伪造 sender、并发入队、跨 TeamRuntime 隔离。
- 两个已发布 TeamAgent 的 handle 与工具均完成收发；真实 RuntimeFactory 的 ToolExecutor 调用也可在不调用模型的情况下路由消息。
- 工具仅存在于 TeamAgent per-instance policy；Master 与普通 Subagent 的通用工具集合不包含消息工具。伪造的 `ToolContext.runtime` 即便携带相同 agent_id，也无法使用 wrapper 的 handle。
- 收发测试以断言阻止 `TeamAgent.run()` 与 `MemberRegistry.transition()` 被调用；消息路径没有 query loop、后台线程或任务协作行为。
- Phase 3、SC-03 及新增测试项仍未勾选，等待 Completion Review。

## Design Deltas

DD-01～DD-04 已按接受的审阅结果实现。实现审阅额外发现 Registry 会 trim ID，而原 bus 以未 trim ID 路由；现要求消息 ID 完全匹配规范 Registry ID，并已写入 `../04_contracts.md`。工具错误文本现包含异常类型名，以满足 DD-04 对 typed error 呈现的要求。

## Remaining Risks

- 消息仅保存在内存，进程结束后不恢复；此行为符合 ADR-011。
- Bus 锁保护单次队列操作，不承诺与未来并发 shutdown 的跨模块原子性；Phase 5 需重新审阅该竞态。
- one-message-one-turn 的执行触发、MemberState 的执行期协调、任务协作与 teardown 仍留待后续阶段；本轮不运行真实模型 smoke。

## Outcome

TASK-04 实现与自动验证已完成，当前状态为 `In Progress / Awaiting Completion Review`。完成审阅接受前，Phase 3、SC-03 与本任务新增测试项维持未勾选。
