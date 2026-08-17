# Interaction 交互

Interaction 用于隔离 Agent Runtime 与具体的交互界面。Runtime 只关心“获取输入”和“请求审批”的结果，不直接读取 CLI、Web 或其他前端的输入流。

# 1. Interaction 的作用

```text
query loop → Interaction Protocol → CLI / Web / API
```

Interaction 与 EventSink 的职责不同：

- Interaction 负责等待用户并返回结果。
- EventSink 负责发布已经发生的事实。

例如工具审批时，Interaction 等待用户选择，EventSink 同时记录审批请求和审批结果。

# 2. 审批数据结构

## 2.1 `ApprovalRequest`

`ApprovalRequest` 描述需要用户确认的工具调用：

```python
request = ApprovalRequest(
    tool_call_id="call-1",
    tool_name="powershell",
    arguments={"command": "Remove-Item test.py"},
    reason="潜在破坏性指令",
)
```

字段包括：

- `tool_call_id`：模型生成的工具调用 ID。
- `tool_name`：工具名称。
- `arguments`：工具参数字典。
- `reason`：请求审批的原因。

## 2.2 `ApprovalResponse`

```python
ApprovalResponse(
    approved=True,
    message=None,
)
```

字段包括：

- `approved`：是否批准执行。
- `message`：可选的拒绝或中断原因。

两个对象都是不可变的 dataclass，避免交互实现返回后被 Runtime 意外修改。

# 3. `Interaction` Protocol

```python
class Interaction(Protocol):
    def get_user_input(self) -> str:
        ...

    def request_approval(
        self,
        request: ApprovalRequest,
    ) -> ApprovalResponse:
        ...
```

`get_user_input()` 用于顶层 Agent 入口获取下一条用户消息；`request_approval()` 只在 PreToolUse Hook 返回 `ASK` 且当前策略允许询问用户时调用。

# 4. 当前实现

## 4.1 `CliInteraction`

CLI 实现负责显示审批信息并读取确认输入：

1. 显示 `reason`。
2. 显示工具名称和参数。
3. 读取“是否继续？(y/N)：”。
4. 只有 `y` 或 `yes`（不区分大小写）返回 `approved=True`。
5. 空输入、`n`、`no` 或其他输入返回 `approved=False`。
6. `EOFError` 或 `KeyboardInterrupt` 返回 `approved=False`，消息为“审批输入被中断”。

普通用户输入使用默认提示符 `">> "`。

## 4.2 `NonInteractiveInteraction`

这是 `RuntimeFactory` 的默认交互实现：

- `request_approval()` 总是拒绝，消息为“当前 Runtime 不支持交互式审批”。
- `get_user_input()` 抛出 `EOFError`。

因此没有显式注入交互实现的 Runtime 不会在后台等待用户，也不会默认批准高风险工具调用。

# 5. 审批流程

工具调用的审批发生在 PreToolUse Hook 之后、ToolExecutor 之前：

```mermaid
sequenceDiagram
    participant Loop as query_loop
    participant Hook as HookManager
    participant Events as EventSink
    participant UI as Interaction
    participant Tool as ToolExecutor

    Loop->>Hook: PRE_TOOL_USE(ctx, block)
    Hook-->>Loop: HookResult(ASK)

    alt policy.can_ask_user == false
        Loop->>Events: tool.blocked
    else ask user
        Loop->>Events: approval.requested
        Loop->>UI: request_approval(request)
        UI-->>Loop: ApprovalResponse
        Loop->>Events: approval.resolved
        alt approved
            Loop->>Events: tool.started
            Loop->>Tool: execute(name, arguments)
            Tool-->>Loop: output
            Loop->>Events: tool.completed
        else rejected
            Loop->>Events: tool.blocked
        end
    end
```

当 Hook 返回 `BLOCK` 时不会创建 `ApprovalRequest`，也不会触发 `approval.requested` 或 `approval.resolved`，而是直接记录 `tool.blocked`。

# 6. 自定义 Interaction

Web 或 API 前端可以实现同一个 Protocol：

```python
class WebInteraction:
    def get_user_input(self) -> str:
        return read_from_request()

    def request_approval(
        self,
        request: ApprovalRequest,
    ) -> ApprovalResponse:
        return wait_for_frontend_decision(request)
```

创建 Runtime 时注入：

```python
runtime = RuntimeFactory.create(
    agent_name="web-agent",
    policy=policy,
    state=agent_state,
    memory_policy=memory_policy,
    workspace=workspace,
    interaction=WebInteraction(),
)
```

自定义实现只需要遵守两个方法的输入输出约定，不需要修改 `query_loop()`、Hook 或 Event 模块。
