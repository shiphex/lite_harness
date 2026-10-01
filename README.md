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

## 2. Agent Team

Agent Team 沿用主程序的模型配置，可连接受支持的模型提供方 API，也可连接符合相应协议的本地模型服务。运行前根据所用服务设置 `--api`、`--model_url`、`--model_name` 和鉴权参数 `--api_key`；参数用法见第 1 节。模型地址、名称和鉴权要求以所用服务为准。

Master 可在同一会话创建 TeamAgent、分配团队任务、查询状态，并在安全收尾后退出。TeamAgent 复用现有 query loop；团队成员、消息和任务状态由独立的 TeamRuntime 管理。架构见 [Agent Team](doc/architecture/agent_team.md)。

默认 pytest 不访问模型。单成员 smoke 和双成员/恢复场景须手动运行；服务检查、完整命令、JSON 通过标准以及交互式 Master 操作见 [Agent Team 运行测试笔记](doc/note/s13_agent_team_testing_note.md)。笔记中的模型和本地服务仅是一次验收所用的示例，换用其他模型或提供方 API 时需调整连接与鉴权参数；真实令牌不要写入文档或提交到仓库。

## 3. 运行主线

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

## 4. 项目结构

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
├── team/                        # TeamRuntime、成员生命周期、通信和任务编排
├── scripts/                     # 显式运行的本地模型验收入口
├── config/                      # 启动参数和运行配置
├── doc/architecture/            # 架构说明文档
├── doc/note/                    # 操作与学习笔记
├── tests/                       # 单元测试和流程测试
├── main.py                      # 程序启动入口
├── pyproject.toml               # 项目和依赖配置
└── uv.lock                      # 依赖锁定文件
```

## 5. 架构文档

- [Architecture Principles](doc/architecture/principles.md)：项目架构原则。
- [Agent](doc/architecture/agent.md)：Agent 顶层入口、输入循环和输出处理。
- [Agent Loop](doc/architecture/agent_loop.md)：query loop、工具调用和压缩生命周期。
- [Runtime](doc/architecture/runtime.md)：Runtime、RunPolicy、state 和组件组装。
- [Event](doc/architecture/event.md)：事件类型、EventSink 和事件顺序。
- [Hook](doc/architecture/hook.md)：HookManager、权限检查和 Hook 生命周期。
- [Interaction](doc/architecture/interaction.md)：用户输入、审批请求和交互实现。
- [Model API Contract](doc/architecture/model_api_contract.md)：统一模型请求、响应和适配器协议。
- [Agent Team](doc/architecture/agent_team.md)：团队组装、消息、任务与生命周期。
- [Testing](doc/architecture/testing.md)：离线与显式真实模型测试的边界。

## 6. 已知问题

1. 用户拒绝执行指令后，Agent 仍可能多次尝试执行相同或相似的命令，然后再次询问用户。
2. 记忆加载不需要内容或加载失败时，当前流程仍可能等待较长时间。

## 7. 项目参考

- [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code)
- [Claw Code](https://github.com/ultraworkers/claw-code)
- [-awesome-cc-harness](https://github.com/WanLanglin/-awesome-cc-harness)
