# Event 事件

Event 用于记录 Runtime 中已经发生的结构化事实。它面向 CLI、日志、测试和未来的 Web 客户端，不负责发起动作，也不负责改变 query loop 的控制流。

# 1. Event 的作用

```text
Runtime 中发生事实 → Event → EventSink → CLI / Log / Web / Test
```

Event 和 Hook 的区别是：

- Event 是结果通知，例如“工具已经开始执行”。
- Hook 是执行过程中的扩展点，可以返回 `BLOCK` 或 `ASK`，影响后续流程。

# 2. `EventType`

当前事件类型如下：

| Event | 意义 | 当前触发位置 |
| ---- | ---- | ---- |
| `system.message` | 系统提示信息 | `master_agent()` 启动时。 |
| `run.started` | 一次 `query_loop()` 开始 | `query_loop()` 入口。 |
| `run.completed` | 一次 query loop 结束 | 正常完成、达到轮次限制或上下文恢复失败时。 |
| `turn.started` | 新一轮 query loop 开始 | `state.turn_count` 增加后。 |
| `assistant.message` | Assistant 文本消息 | `master_agent()` 处理完 query loop 返回的历史消息后。 |
| `tool.requested` | 模型提出工具调用 | `execute_tool()` 处理工具块时。 |
| `tool.started` | 工具实际开始执行 | PreToolUse 和审批通过后。 |
| `tool.completed` | 工具执行完成 | 工具执行和 PostToolUse 后。 |
| `tool.blocked` | 工具调用被阻止 | Hook 拒绝、审批拒绝或 Agent 不允许审批时。 |
| `approval.requested` | 请求用户审批 | PreToolUse 返回 `ASK` 且允许询问用户时。 |
| `approval.resolved` | 审批已经得到结果 | `Interaction.request_approval()` 返回后。 |
| `compact.started` | 压缩开始 | 自动压缩、反应式压缩或 `compact` 工具。 |
| `compact.completed` | 压缩完成 | 对应压缩操作结束后。 |
| `error` | 已处理的错误 | 反应式压缩后仍无法继续时。 |

`EventType` 的值使用点号命名，例如 `EventType.TOOL_COMPLETED == "tool.completed"`。

# 3. `Event`

`Event` 是不可变的 dataclass：

| 字段 | 意义 |
| ---- | ---- |
| `type` | `EventType` 事件类型。 |
| `session_id` | 事件所属会话。 |
| `agent_id` | 产生事件的 Agent。 |
| `turn` | 事件创建时的 `runtime.state.turn_count`。 |
| `data` | 当前事件特有的数据字典。 |
| `event_id` | 每个事件独立的随机 ID。 |
| `timestamp` | UTC 时区的创建时间。 |

事件本身不能被修改：

```python
event = Event(
    type=EventType.TOOL_COMPLETED,
    session_id="session-1",
    agent_id="agent-1",
    data={"tool_name": "read_file", "output": "ok"},
)
```

`data` 当前没有统一的强类型对象，因为不同事件需要携带的数据不同。常见数据包括 `tool_call_id`、`tool_name`、`arguments`、`output`、`reason` 和 `trigger`。

# 4. `make_event()`

调用方通常从 Runtime 创建事件：

```python
runtime.events.emit(
    event.make_event(
        runtime,
        event.EventType.TOOL_COMPLETED,
        tool_call_id="call-1",
        tool_name="read_file",
        output="ok",
    )
)
```

`make_event()` 自动补充：

- `runtime.session_id`
- `runtime.agent_id`
- `runtime.state.turn_count`
- 随机 `event_id`
- 当前 UTC `timestamp`

因此事件 payload 只需要传入当前事件特有的数据。

# 5. `EventSink`

`EventSink` 只有一个方法：

```python
class EventSink(Protocol):
    def emit(self, event: Event) -> None:
        ...
```

项目提供四种实现：

| Sink | 用途 |
| ---- | ---- |
| `NullEventSink` | 默认实现，忽略事件。适合不需要输出事件的 Runtime。 |
| `FanoutEventSink` | 按注册顺序把同一个事件发送给多个 Sink。 |
| `MemoryEventSink` | 把事件保存到 `events` 列表，适合测试和调试。 |
| `CliEventSink` | CLI 模块提供的实现，把部分事件渲染成终端输出。 |

例如同时输出 CLI 并保存测试记录：

```python
events = FanoutEventSink(
    CliEventSink(),
    MemoryEventSink(),
)
```

# 6. 事件顺序

一次工具调用通常经过以下事件顺序：

```text
tool.requested
    ├── Hook BLOCK / 审批拒绝 → tool.blocked
    └── Hook CONTINUE / 审批通过
            ├── tool.started
            └── tool.completed
```

一次没有工具调用的正常回答通常是：

```text
run.started
→ turn.started
→ compact.started / compact.completed
→ run.completed
→ assistant.message   # 由顶层 Agent 入口处理输出时发送
```

`approval.requested` 和 `approval.resolved` 位于 `tool.requested` 与最终的 `tool.started` 或 `tool.blocked` 之间。审批流程见 [interaction.md](./interaction.md)。

# 7. 消费端注意事项

- EventSink 的 `emit()` 当前是同步调用。
- EventSink 不应修改 Event，也不应通过事件反向控制 query loop。
- `CliEventSink` 只处理部分事件；未处理的事件会被忽略。
- Web、SSE、WebSocket 或 JSONL 日志可以实现新的 EventSink，不需要修改 Runtime 或 query loop。
- 测试可以使用 `MemoryEventSink` 检查事件类型、顺序和 `data` 内容。
