# cron scheduler

任务按时启动功能

# 1. 如何实现任务按时启动功能

将任务以五段式 Cron 表达式注册到 cron_queue 中：
``` python
cron:   0 9 * * *
prompt: run tests
```
队列处理线程等到 Agent 空闲后启动一轮 Agent Loop，模型随后可以调用 Bash 执行任务。

# 2. 工作原理

## 2.1 任务注册
``` python
@dataclass
class CronJob:
    id: str
    cron: str           # 决定何时触发任务
    prompt: str         # 任务描述，触发后交给 Agent 的任务
    recurring: bool
    durable: bool
    pending_delivery: bool = False      # 表示任务已经到期但尚未被模型接收
    last_fired: str | None = None       # 防止同一分钟重复入队
```

## 2.2 五段式 Cron 表达式
``` text
分钟  小时  日  月  星期
  *    *   *   *   *      每分钟
  0    9   *   *   *      每天 09:00
 */5   *   *   *   *      每 5 分钟
  0    9   *   *  1-5     工作日 09:00

#  支持 *、*/N、N、N-M 和 N,M,...
```
schedule_job() 会在保存任务前调用 validate_cron()，拒绝字段数量或取值范围不正确的表达式。

## 2.3 到期后先入队

- 调度线程每秒读取一次本地时间
- 表达式匹配且任务在当前分钟尚未触发时，_enqueue_due_job() 先保存 pending_delivery 和 last_fired
- 再把任务放进内存队列
- 持久化失败时，_enqueue_due_job() 会恢复原来的状态，不会把只存在于内存中的任务暴露给队列处理线程。

## 2.4 Agent 空闲后再交付
- queue_processor_loop() 不负责判断时间
- 它只检查队列，并用 agent_lock 避免定时任务与用户正在进行的回合同时修改会话
- Agent Loop 从队列取出到期任务，并把它们作为新的用户消息追加到会话中
- 模型调用失败时，这些消息会从当前会话中移除，任务重新放回队列。
- 模型成功接收后，一次性任务会被删除，周期任务则清除 pending_delivery，等待下一次匹配。

