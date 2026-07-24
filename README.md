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
├── .agent/
|   └── skills/
├── core/
│   ├── loop.py
|   └── agent.py
├── api/
│   ├── wiki_client.py
│   ├── openai_api.py
│   └── anthropic_api.py
├── cli/
├── builtin/
├── hook/
├── tools/
├── config/
└── tests/
```

# 本项目参考
- [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code)
- [Claw Code](https://github.com/ultraworkers/claw-code)

# 暂时未解决的问题
1. 当用户拒绝执行指令时，Agent 依然还会尝试多次执行该命令或类似命令，然后询问用户是否继续。