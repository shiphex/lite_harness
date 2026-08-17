# lite_harness

一个精简的最小 Agent Harness，用于学习和验证 Agent 的基本设计。项目包含模型调用、工具执行、记忆管理、Hook、事件和交互等抽象，重点是保持核心流程简单、可观察、容易测试。

## 1. 快速开始

项目使用 [uv](https://docs.astral.sh/uv/getting-started/) 管理依赖。

在 PowerShell 中安装依赖并运行：

```powershell
uv sync
.venv\Scripts\Activate.ps1
uv run main.py
```

当前默认模型配置为：

```text
api:       anthropic
model_url: http://localhost:8000
api_key:   no-key
model_name: claude-fable-5
```

默认地址是项目的本地模型服务配置，不代表项目自带模型服务。也可以通过命令行参数覆盖配置：

```powershell
uv run main.py `
  --api anthropic `
  --model_url http://localhost:8000 `
  --api_key no-key `
  --model_name claude-fable-5
```

支持的 API 类型包括：`anthropic`、`openai`、`gemini` 和 `langchain`。

## 2. 运行主线

CLI 负责接收用户输入和显示输出，Runtime 负责组装运行时依赖，query loop 负责模型调用和工具编排：

```text
CLI → RuntimeFactory → query_loop → Model / Hook / Tool → EventSink
```

一次典型运行包含以下步骤：

1. 创建 `AgentRuntime`，注入模型、工具、记忆、Hook、事件和交互组件。
2. 获取用户输入并运行 `UserPromptSubmit` Hook。
3. `query_loop()` 调用模型，处理模型消息和工具调用。
4. `PreToolUse` Hook 检查工具权限，必要时通过 Interaction 请求审批。
5. `ToolExecutor` 执行工具，EventSink 发布运行事件。
6. 没有新的工具调用时运行 `Stop` Hook，并返回本轮状态。

## 3. 项目结构

```text
lite_harness/
├── api/                         # 模型请求、响应和厂商适配器
│   ├── contract.py              # ModelRequest、ModelResponse 等统一类型
│   ├── *_adapter.py             # Anthropic、OpenAI、Gemini 等适配器
│   └── old_api/                 # 旧版模型 API，保留用于兼容
├── core/                        # Agent 核心流程
│   ├── runtime.py               # AgentRuntime、RunPolicy、state
│   ├── loop.py                  # query_loop 工作循环
│   └── agent.py                 # CLI Agent 顶层入口
├── builtin/                     # 内置记忆、提示词、产物和恢复逻辑
├── cli/                         # CLI 交互和事件渲染
├── event/                       # Event、EventSink 和 Interaction Protocol
├── hook/                        # HookManager 和默认 Hook
├── tools/                       # 工具注册、执行和上下文压缩
├── config/                      # 启动参数和运行配置
├── doc/architecture/            # 架构说明文档
├── tests/                       # 单元测试和流程测试
├── main.py                      # 程序启动入口
├── pyproject.toml               # 项目和依赖配置
└── uv.lock                      # 依赖锁定文件
```

## 4. 架构文档

- [Architecture Principles](doc/architecture/principles.md)：项目架构原则。
- [Runtime](doc/architecture/runtime.md)：Runtime、RunPolicy、state 和组件组装。
- [Event](doc/architecture/event.md)：事件类型、EventSink 和事件顺序。
- [Hook](doc/architecture/hook.md)：HookManager、权限检查和 Hook 生命周期。
- [Interaction](doc/architecture/interaction.md)：用户输入、审批请求和交互实现。
- [Model API Contract](doc/architecture/model_api_contract.md)：统一模型请求、响应和适配器协议。

## 5. 已知问题

1. 用户拒绝执行指令后，Agent 仍可能多次尝试执行相同或相似的命令，然后再次询问用户。
2. 记忆加载不需要内容或加载失败时，当前流程仍可能等待较长时间。

## 6. 项目参考

- [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code)
- [Claw Code](https://github.com/ultraworkers/claw-code)
- [-awesome-cc-harness](https://github.com/WanLanglin/-awesome-cc-harness)
