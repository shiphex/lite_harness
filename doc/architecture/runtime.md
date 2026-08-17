# Runtime 运行时

Runtime 用于保存一次 Agent 运行所需要的状态、配置和组件。它不是 Agent 策略本身，而是把 query loop 需要的依赖放在一起。

# 1. Runtime 的作用

`AgentRuntime` 是 query loop 的运行时依赖容器：

```text
RunPolicy + state + 运行组件 → AgentRuntime → query_loop()
```

query loop 不直接创建模型、工具、Hook 或交互对象，而是从 Runtime 中取得这些组件。这样 CLI、测试和其他调用方可以注入不同实现。

# 2. ID 和运行范围

| 字段 | 意义 |
| ---- | ---- |
| `session_id` | 整个会话的 ID。一个会话可以包含多次用户输入。 |
| `agent_name` | Agent 的显示名称。 |
| `agent_id` | 当前 Agent Runtime 的 ID，由 `agent_name` 和随机字符串组成。 |
| `state.turn_count` | 当前 query loop 的轮次。每次调用 `query_loop()` 前，顶层入口会重新置零。 |

当前 Runtime 没有 `run_id` 字段。一次用户请求由 `query_loop()` 的一次调用表示；事件本身还有独立的 `event_id`。

# 3. `RunPolicy`

`RunPolicy` 用于配置 query loop。它在循环中作为配置使用，运行过程中的变化记录在 `state` 中。

主要参数包括：

- `max_turns`：最大循环次数。大于 0 时启用轮次限制。
- `prompt`：静态提示词配置。
- `model`：默认模型配置。
- `fallback_model`：模型失败时使用的备用模型配置。
- `tools_list`：允许模型使用的工具定义列表。
- `tool_handler`：工具名称到实际执行函数的映射。
- `can_ask_user`：是否允许进入用户审批流程。

当前模型保存在 `state.current_model` 中。发生模型切换时，更新的是运行状态，不直接改写 `RunPolicy.model`。

# 4. `state`

`state` 记录 query loop 的可变状态：

| 字段 | 意义 |
| ---- | ---- |
| `messages` | 当前会话消息列表。 |
| `context` | 记忆、系统状态等上下文参数。 |
| `max_output_tokens` | 当前模型请求的最大输出 token 数。 |
| `toolUse_prompt` | 动态工具调用提示词。 |
| `turn_count` | 当前 query loop 轮次。 |
| `transition` | 上一次循环迭代的原因。 |
| `max_output_tokens_override` | 是否已经覆盖默认输出预算。 |
| `recovery_count` | 输出过长恢复次数。 |
| `has_attempted_reactive_compact` | 是否已经尝试过反应式压缩。 |
| `current_model` | 当前实际使用的模型配置。 |
| `consecutive_529` | 连续出现 529 错误的次数。 |

`query_loop()` 返回：

```python
result_state, status = query_loop(runtime)
# status 例如：
# {"reason": "completed"}
# {"reason": "max_turns"}
# {"reason": "prompt_too_long"}
```

当前实现会规范化以上三种结束状态。其他未被恢复的异常会继续向调用方抛出，不会被统一转换成旧文档中的状态名称。

# 5. Runtime 组件

`AgentRuntime` 当前包含以下组件：

| 字段 | 类型 | 作用 |
| ---- | ---- | ---- |
| `paths` | `RuntimePaths` | 保存工作目录、会话目录、工具结果目录和 transcript 目录。 |
| `prompt` | `PromptBuilder` | 构建系统提示词。 |
| `memory` | `MemoryManager` | 加载、提取和整理记忆。 |
| `artifacts` | `ArtifactStore` | 保存工具结果和 transcript 相关产物。 |
| `hooks` | `HookManager` | 注册并运行当前 Agent 的 Hook。 |
| `events` | `EventSink` | 发布 Runtime 事件。 |
| `tools` | `ToolExecutor` | 校验并执行工具。 |
| `interaction` | `Interaction` | 获取用户输入和处理审批请求。 |

这些组件的职责分别见 [event.md](./event.md)、[hook.md](./hook.md) 和 [interaction.md](./interaction.md)。

# 6. `RuntimePaths`

`RuntimePaths.create()` 根据工作目录、`session_id` 和 `agent_id` 组织运行文件：

```text
workspace/
└── .agents/
    └── runs/
        └── {session_id}/
            └── {agent_id}/
                ├── tool_results/
                └── transcripts/
```

记忆目录不属于本次 Agent 的运行目录，而是位于：

```text
workspace/.agents/.memory/{memory_namespace}/
```

# 7. `RuntimeFactory`

`RuntimeFactory.create()` 负责组装一套完整 Runtime：

1. 生成缺省的 `session_id` 和 `agent_id`。
2. 创建 `RuntimePaths`。
3. 创建 `PromptBuilder`、`MemoryManager` 和 `ArtifactStore`。
4. 创建 `ToolExecutor`，并注入 `tool_handler` 和 `tools_list`。
5. 未传入组件时，使用默认实现：
   - `HookManager`：`create_default_hooks()`。
   - `EventSink`：`NullEventSink()`。
   - `Interaction`：`NonInteractiveInteraction()`。
6. 返回 `AgentRuntime`。

测试或其他前端可以直接注入组件：

```python
runtime = RuntimeFactory.create(
    agent_name="agent",
    policy=policy,
    state=agent_state,
    memory_policy=memory_policy,
    workspace=workspace,
    hooks=test_hooks,
    events=MemoryEventSink(),
    interaction=custom_interaction,
)
```

# 8. 一次运行的关系

CLI 顶层入口负责创建 Runtime 和接收用户输入；`query_loop()` 负责模型调用与工具编排；具体组件负责各自的副作用或观察行为。

```mermaid
sequenceDiagram
    participant Client as CLI / Client
    participant Runtime as AgentRuntime
    participant Loop as query_loop
    participant Model as Model Adapter
    participant Hook as HookManager
    participant Tool as ToolExecutor
    participant Sink as EventSink
    participant User as Interaction

    Client->>Runtime: RuntimeFactory.create()
    Client->>Runtime: 获取输入、运行 UserPromptSubmit Hook
    Client->>Loop: query_loop(runtime)
    Loop->>Sink: run.started / turn.started
    Loop->>Model: complete(ModelRequest)
    Model-->>Loop: ModelResponse
    Loop->>Hook: PreToolUse / Stop
    Hook-->>Loop: HookResult
    Loop->>User: request_approval()
    User-->>Loop: ApprovalResponse
    Loop->>Tool: execute(name, arguments)
    Tool-->>Loop: output
    Loop->>Sink: tool.* / approval.* / compact.*
    Loop-->>Client: state, status
```

# 9. 和其他模块的边界

- Runtime 只保存组件和状态，不实现权限策略、工具逻辑或具体 UI。
- Hook 决定工具调用是否继续、是否需要审批；真正的审批由 Interaction 完成。
- EventSink 只发布已经发生的事实，不替代 Interaction，也不控制 query loop。
- 所有实际工具执行都经过 Runtime 中的 `ToolExecutor`。
