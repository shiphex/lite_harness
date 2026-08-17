# Hook 钩子

Hook 是 Runtime 中的扩展点。它在用户输入、工具调用和循环结束等位置执行自定义逻辑，可以记录信息、检查权限，或要求 query loop 改变后续行为。

# 1. Hook 和 Event 的区别

```text
Hook：在动作发生前或发生后执行，可返回结果影响流程
Event：动作已经发生后发布，只描述事实
```

例如：

- `PreToolUse` Hook 可以阻止 `powershell` 工具。
- `tool.blocked` Event 记录工具调用最终被阻止。

# 2. Hook 类型

当前 `HookManager` 支持四种 `HookEvent`：

| HookEvent | 值 | 参数 | 用途 |
| ---- | ---- | ---- | ---- |
| `USER_PROMPT_SUBMIT` | `user_prompt_submit` | `ctx, query` | 用户输入交给模型前执行。 |
| `PRE_TOOL_USE` | `pre_tool_use` | `ctx, block` | 工具执行前检查权限或请求审批。 |
| `POST_TOOL_USE` | `post_tool_use` | `ctx, block, output` | 工具执行后观察结果。 |
| `STOP` | `stop` | `ctx, messages` | 模型没有工具调用时，决定是否结束当前运行。 |

Hook Event 和 EventType 是两套不同的枚举：前者表示回调扩展点，后者表示已经发生的运行事实。

# 3. Hook 数据结构

## 3.1 `HookContext`

`HookContext` 从 Runtime 提取不会频繁变化的运行信息：

- `session_id`
- `agent_id`
- `agent_name`
- `turn_count`
- `workspace`

通过 `make_hook_context(runtime)` 创建：

```python
ctx = make_hook_context(runtime)
result = runtime.hooks.run(
    HookEvent.PRE_TOOL_USE,
    ctx,
    block,
)
```

## 3.2 `HookAction`

| Action | 意义 |
| ---- | ---- |
| `CONTINUE` | 当前 Hook 不阻止流程，继续运行后续 Hook。 |
| `BLOCK` | 停止 Hook chain，并阻止后续动作。 |
| `ASK` | 停止 Hook chain，要求调用方进入审批流程。 |

## 3.3 `HookResult`

```python
HookResult(
    action=HookAction.ASK,
    message="潜在破坏性指令",
)
```

字段包括：

- `action`：默认为 `HookAction.CONTINUE`。
- `message`：阻止或审批时显示给调用方的原因。
- `blocked`：是否为 `BLOCK`。
- `approval_required`：是否为 `ASK`。

# 4. `HookManager`

`HookManager` 按注册顺序保存每种事件的回调：

```python
manager.register(
    HookEvent.PRE_TOOL_USE,
    permission_hook,
)
```

触发时依次调用回调：

1. 回调返回 `None`，继续下一个回调。
2. 回调返回 `CONTINUE`，继续下一个回调。
3. 回调返回 `BLOCK` 或 `ASK`，立即停止当前 Hook chain，并返回该结果。
4. 所有回调都结束后，返回默认的 `HookResult()`。

```python
result = manager.run(
    HookEvent.PRE_TOOL_USE,
    ctx,
    block,
)
```

# 5. Hook 在 query loop 中的行为

## 5.1 用户输入

`master_agent()` 读取用户输入后触发 `USER_PROMPT_SUBMIT`。当前默认的 `context_inject_hook` 输出工作目录信息，不修改用户输入。

## 5.2 工具执行前

`PRE_TOOL_USE` 的结果由 query loop 处理：

- `CONTINUE`：继续执行工具。
- `BLOCK`：不执行工具，生成被阻止的工具结果，并发送 `tool.blocked`。
- `ASK`：如果 `policy.can_ask_user` 为 `False`，直接阻止；否则创建 `ApprovalRequest`，交给 Interaction。

审批通过后才会发送 `tool.started` 并调用 `ToolExecutor`。审批拒绝会生成工具结果并发送 `tool.blocked`。

## 5.3 工具执行后

`POST_TOOL_USE` 在 `ToolExecutor.execute()` 返回后触发，参数包含工具块和输出。当前主流程使用它进行观察，例如检查输出长度；该 Hook 的返回值目前不会改变已经完成的工具执行。

## 5.4 停止判断

当模型响应没有 `tool_use` 时，query loop 触发 `STOP`：

- `HookAction.CONTINUE`：发送 `run.completed`，返回 `{"reason": "completed"}`。
- `HookAction.BLOCK`：把 `HookResult.message` 作为新的用户消息加入历史，然后继续下一轮。

当前 `STOP` 调用只检查 `force.blocked`。如果 Stop Hook 返回 `ASK`，不会自动进入 Interaction 审批流程；需要继续运行时应返回 `BLOCK`。

# 6. 默认 Hook

`create_default_hooks()` 注册以下 Hook：

| Hook | 默认实现 | 作用 |
| ---- | ---- | ---- |
| `USER_PROMPT_SUBMIT` | `context_inject_hook` | 输出当前工作目录信息。 |
| `PRE_TOOL_USE` | `permission_hook` | 检查拒绝列表、工作目录边界和潜在破坏性指令。 |
| `POST_TOOL_USE` | `large_output_hook` | 输出过大时发出警告。 |
| `STOP` | `summary_hook` | 统计工具调用次数并输出会话摘要信息。 |

`log_hook` 已实现，但当前没有注册到默认 `HookManager`。

权限 Hook 的基本结果是：

```text
拒绝列表命令       → BLOCK
潜在破坏性命令     → ASK
普通安全命令       → CONTINUE
```

安全底线应由权限 Hook 和 ToolExecutor 共同保证，普通项目配置不应通过 Hook 放宽拒绝规则。

# 7. 旧版全局 Hook API

`hook.hook_handler` 仍保留以下全局 API：

```python
register_hook("PreToolUse", callback)
result = trigger_hooks("PreToolUse", ctx, block)
```

它使用全局 `HOOK` 字典和 PascalCase 事件名，主要用于兼容旧代码。当前 `AgentRuntime` 保存的是独立的 `HookManager`，主 Runtime 流程通过 `runtime.hooks.run()` 执行 Hook。

新代码应优先使用 `HookEvent`、`HookManager.register()` 和 `HookManager.run()`，避免不同 Runtime 之间共享全局回调。
