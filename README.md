# 1. Agent 设计方案
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
├── validators/
├── config/
└── tests/
```

# 暂时未解决的问题
1. 当用户拒绝执行指令时，Agent 依然还会尝试多次执行该命令或类似命令，然后询问用户是否继续。