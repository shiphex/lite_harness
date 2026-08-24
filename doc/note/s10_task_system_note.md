# 可恢复的任务系统

- 让每个任务都有独立的 ID 和状态，blockedBy 记录前置任务，owner 记录负责执行的 Agent。
- 通过储存为 JSON 文件（`.tasks/{id}.json`），实现任务的持久化存储。
- 更新模式：对单条记录执行创建、读取、更新、列举操作。



## 1.1 Task: 数据结构
``` python
@dataclass
class Task:
    id: str
    subject: str
    description: str
    status: str          # pending | in_progress | completed
    owner: str | None    # 负责当前任务的 Agent
    blockedBy: list[str] # 依赖的任务 ID 列表
```

ID 使用 task_ 加 8 位随机十六进制字符生成。创建文件时使用排他写入；如果 ID 已存在，就重新生成。


## 1.2 Task 系统的依赖关系

``` mermaid
flowchart TD
    A[✓ <b>schema</b> <br> complete] --> B[● <b>endpoints</b> <br> in_progress · owner: agent-1]
    A --> C[○ <b>docs</b> <br> pending · blockdeBy: schema ✓]
    B --> D[○ <b>tests</b> <br> blockdeBy: endpoints ●]
    C --> E[○ <b>deploy</b> <br> blockdeBy: tests, docs]
    D --> E
```

其中箭头方向为依赖方向

## 1.3 相关函数
- create_task: 创建任务
- update_task: 使用返回的 ID 添加依
- can_start: 依赖检查
- claim_task: 认领任务
- complete_task: 完成与解锁
- get_task: 查看完整细节

## 1.4 状态机
``` text
pending ──claim──→ in_progress ──complete──→ completed
```
claim / complete 是动作，pending / in_progress / completed 是状态：
- claim_task: pending → in_progress。设置 owner，开始工作。
- complete_task: in_progress → completed。把任务标记为完成，并解锁下游。
