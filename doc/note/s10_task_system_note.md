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


# 2. 工具系统

## 2.1 创建任务
TaskStore.create 检查 subject，分配随机 ID，再把任务写入 .tasks/{id}.json。新任务的 blockedBy 固定为空，工具结果会把运行时生成的 ID 返回给模型。

## 2.2 更新任务
更新任务将 create_task 返回的 ID 作为参数，调用 update_task 为以及存在的任务添加依赖关系。

任务图采用两阶段构建：
- 先创建所有节点
- 再使用 create_task 返回的 ID 调用 update_task 添加边。

模型可能在一条回复里同时发出多个工具调用，而这些同级调用在任何工具结果产生前就已经确定，因此某个 create_task 无法直接使用另一个调用刚生成的 ID。

## 2.3 列出所有任务
list_tasks 返回所有任务的 ID、subject、status、owner 和 blockedBy。

## 2.4 run_get_task: 查看完整细节
list_tasks 只显示一行摘要。get_task 返回完整的任务 JSON，包括 description 和依赖细节。跨会话恢复时，Agent 需要读取完整描述才能继续工作。

## 2.5 认领任务
Agent 开始做一个任务时，调用 claim_task：设置 owner，状态从 pending → in_progress。owner 字段记录谁认领了这个任务。如果任务不是 pending，或者依赖没有完成，就拒绝认领。

## 2.6 完成与解锁
任务做完后，设为 completed。同时扫描所有其他任务，找出刚刚被解锁的下游任务

### 2.6.1 can_start: 依赖检查
- 一个任务只能在它的 blockedBy 全部 completed 之后才能开始
- incomplete_dependencies 读取每个前置任务。只要有一个不是 completed，或者对应文件已经不存在，任务就不能认领。


# 3. 运行流程示例
``` python
# 第一阶段：创建所有节点并取得运行时 ID
schema = create_task("setup database schema")
endpoints = create_task("create API endpoints")
tests = create_task("write tests")
docs = create_task("write docs")

# 第二阶段：使用返回的 ID 建立依赖边
update_task(endpoints.id, addBlockedBy=[schema.id])
update_task(tests.id, addBlockedBy=[endpoints.id])
update_task(docs.id, addBlockedBy=[schema.id])

# Agent 认领第一个可做的任务
claim_task(schema.id)       # ✓ Claimed (无依赖)
complete_task(schema.id)    # ✓ Completed → 解锁 endpoints, docs

claim_task(endpoints.id)    # ✓ Claimed (schema 已完成)
complete_task(endpoints.id) # ✓ Completed → 解锁 tests

claim_task(docs.id)         # ✓ Claimed (schema 已完成)
complete_task(docs.id)      # ✓ Completed

claim_task(tests.id)        # ✓ Claimed (endpoints 已完成)
complete_task(tests.id)     # ✓ Completed
```
每个 create_task 写一个 JSON 文件，update_task、claim_task 和 complete_task 更新文件。  
跨会话时，.tasks/ 目录还在，Agent 读文件就能恢复进度。