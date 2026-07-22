# 0. 项目介绍

一个精简的最小 Agent 实现，用于快速开始使用 Agent 设计方案。

# 1. 快速开始
1. 安装依赖
``` bash
uv sync
```
2. 运行 Agent
``` bash
uv run main.py
```


# 2. Agent 设计方案
Agent 结构：
``` text
Agent
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
├── skills/
├── config/
└── tests/
```

# 暂时未解决的问题
1. 当用户拒绝执行指令时，Agent 依然还会尝试多次执行该命令或类似命令，然后询问用户是否继续。