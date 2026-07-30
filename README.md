# 0. 项目介绍

一个精简的最小 Agent 实现，用于快速开始使用 Agent 设计方案。

# 1. 快速开始

项目使用 uv 管理依赖。若未安装 uv，可参考 [uv 快速开始](https://docs.astral.sh/uv/getting-started/) 安装。

1. 安装依赖并激活虚拟环境
``` bash
uv sync
.venv\Scripts\Activate.ps1
```
2. 运行 Agent
``` bash
uv run main.py
```


# 2. Agent 设计方案
Agent 结构：
``` text
Agent
├── .agent/                     # Agent 目录，包含 Agent 相关文件
|   └── skills/                 # 包含可调用的 skill 文件
├── core/                       # Agent 核心目录
│   ├── loop.py                 # Agent 工作循环
|   └── agent.py                # Agent 主程序
├── api/                        # API 目录，包含与外部服务交互的代码
│   ├── call_model.py           # 调用模型接口
│   ├── response_adapter.py     # 响应适配器
│   ├── langchain_api.py        # Langchain API 接口
│   ├── gemini_api.py           # Gemini API 接口
│   ├── openai_api.py           # OpenAI API 接口
│   └── anthropic_api.py        # Anthropic API 接口(暂时未使用响应适配器)
├── cli/                        # 命令行界面目录
├── builtin/                    # 内置模块目录
├── hook/                       # 钩子模块目录
├── tools/                      # 工具模块目录
├── config/                     # 配置文件目录
└── tests/                      # 测试目录
```

# 本项目参考
- [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code)
- [Claw Code](https://github.com/ultraworkers/claw-code)

# 暂时未解决的问题
1. 当用户拒绝执行指令时，Agent 依然还会尝试多次执行该命令或类似命令，然后询问用户是否继续。
2. 记忆加载时，若不需要加载记忆或者加载失败时，要等待较久时间