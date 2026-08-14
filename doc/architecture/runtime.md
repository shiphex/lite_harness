
## id 配置
- session_id: 整个会话
- agent_id: 谁在执行    
- ~~run_id: 这一次用户请求 / task~~
- turn: query_loop 第几轮


## event runtime

| Event                | 意义             | CLI         | Web            |
| -------------------- | -------------- | ----------- | -------------- |
| `run.started`        | 一次用户任务开始       | 可不显示        | 创建 run         |
| `turn.started`       | query_loop 新一轮 | debug       | 状态             |
| `assistant.message`  | Assistant 完整消息 | 输出文字        | message bubble |
| `tool.requested`     | 模型提出工具调用       | 可选          | tool card      |
| `tool.started`       | 工具真正开始执行       | `$ xxx`     | running        |
| `tool.completed`     | 工具结束           | preview     | success        |
| `tool.blocked`       | Hook/权限阻止      | warning     | blocked        |
| `approval.requested` | 需要用户审批         | y/N         | dialog         |
| `approval.resolved`  | 审批完成           | 可选          | close dialog   |
| `compact.started`    | 开始 compact     | `[compact]` | status         |
| `compact.completed`  | compact 完成     | 可选          | status         |
| `error`              | 错误             | red text    | error card     |
| `run.completed`      | 整个 run 完成      | status      | done           |

``` text
                ┌──────────── UI / Client ────────────┐
                │ CLI │ TUI │ Web │ VSCode │ API     │
                └───────────────┬──────────────────────┘
                                │   
                         Op / Command ↓
                    ┌──────────────────────────┐
                    │      Agent Runtime       │
                    │                          │
                    │      query_loop()        │
                    │         │                │
                    │   ┌─────┴──────┐         │
                    │   │ Hook       │         │
                    │   │ Tool       │         │
                    │   │ Memory     │         │
                    │   │ Model      │         │
                    │   └─────┬──────┘         │
                    │         │                │
                    │      EventSink           │
                    └─────────┬────────────────┘
                              │ Event ↑
                ┌─────────────┼──────────────┐
                ↓             ↓              ↓
          CLI Renderer    JSONL Log       SSE / WS
```