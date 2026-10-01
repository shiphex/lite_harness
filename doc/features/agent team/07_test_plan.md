# 1. 测试框架及策略
- pytest
- architecture/import boundary test
- contract test

Test Strategy：
``` text
Unit / contract / state tests:
    no real LLM

Integration:
    FakeAgentRuntime / FakeLLM

E2E smoke:
    optional real model
```

## 1.1 检查项状态语义

- `[ ]`：测试尚未实现，或尚未通过对应阶段的 Human Review。
- `[√]`：已有自动测试覆盖，并在最近一次已接受的阶段验证中通过。
- 已勾选项目自动成为后续 Phase 的回归测试；Phase 2～5 必须持续保持通过，不重复取消勾选。
- 后续实现导致已勾选测试失败时，当前 Phase 不得完成；应修复回归，或通过 Design Change 流程更新已接受的 Contract、测试及其状态。
- 单项勾选不表示 MVP 最终完成；Phase 6 负责全量集成验证，最终完成状态以 Traceability Matrix 与 Success Criteria 为准。

## 1.2 Phase 6 验证边界

- 按 TASK-07 已接受的 [DD-01～DD-03](_history/TASK-07_human-review.md)，使用 fake runtime/loop 串接 Master bound handler、TeamAgent 消息工具、任务与生命周期；不调用真实模型。真实模型 smoke 仍为 Phase 6 后可选项目。
- 静态架构守卫针对已接受的 import/call 与模块责任边界使用 Python AST；运行时测试继续验证身份、隔离、状态所有权和兼容性。检查不把 TeamRuntime 的具体文件位置设为架构不变量。
- TASK-07 完成审阅已接受，Phase 6 检查项及追踪行已有验证证据并标记 `[√]`；旧检查项与 `01_problem.md` 中已接受的 SC-06/07 勾选不回退。

## 1.3 可选真实模型 smoke 边界

- TASK-08 的 [DD-01～DD-03](_history/TASK-08_human-review.md) 已接受：通过显式入口在临时 workspace 中驱动 Master bound 工具，并由真实模型驱动 TeamAgent 的统一 query_loop。Master 工具调用由 smoke 入口驱动，Master 本身不调用模型。
- 本地配置为 `api=openai`、`model_url=http://127.0.0.1:8000/v1`、`model_name=unsloth/Qwen3.5-4B-GGUF:UD-Q6_K_XL`、无鉴权占位值 `no-key`；服务变化时重新确认。一次 smoke 只执行一个任务，TeamAgent 最多 3 个 turn，每次最多 512 个输出 token。
- `SMOKE-01` 默认不进入 pytest/CI；TASK-08 完成审阅已接受且有真实运行证据，现标记 `[√]`。它是 MVP Phase 6 后的可选增量检查，不更改既有成功标准或已勾选阶段。

## 1.4 扩展真实模型验收边界

- TASK-09 的 `LIVE-01～03` 使用独立的显式入口 `python -m scripts.team_real_model_acceptance`，不进入默认 pytest/CI。每个场景使用临时 workspace、真实 TeamRuntime / Master bound 工具和 TeamAgent 统一 query_loop；Master 工具由脚本驱动。
- 本地配置沿用 §1.3；每名成员每轮最多 6 turn，每次模型请求最多 512 输出 token。只有真实工具执行结果、TaskStore owner / status、MemberRegistry 状态与最终释放全部符合预期才通过；缺少模型回复、错误工具参数、服务/协议错误和 teardown 失败均不得计为通过。
- `LIVE-02/03` 首轮只暴露 `get_team_task` 并限制为 1 turn，以受控方式形成未完成任务；`LIVE-03` 的 fatal 是显式注入的验收故障，不代表真实模型或服务自行故障。交互式 Master 在临时目录中单独观察，不作为脚本化功能验收门槛。
- TASK-09 已实测且完成审阅获接受，`LIVE-01～03` 与追踪行标记 `[√]`；交互式 Master 体验结果继续单列，不改变现有 `SMOKE-01`、Phase 6 或 SC 的已接受状态。审阅证据见 [TASK-09 完成审阅](_history/TASK-09_completion-review.md)。

# 2. State Machine Tests
- [√] STATE-01 STARTING → IDLE allowed
- [√] STATE-02 IDLE → BUSY allowed
- [√] STATE-03 IDLE --shutdown--> STOPPED allowed
- [√] STATE-04 STOPPED → BUSY forbidden，拒绝后仍为 STOPPED
- [√] STATE-05 STOPPED --task_claimed--> BUSY forbidden
- [√] STATE-06 正常 shutdown 后 `MemberRegistry.get(agent_id)` 仍返回 STOPPED member record
- [√] STATE-07 fatal runtime error 后 `MemberRegistry.get(agent_id)` 仍返回 FAILED member record


# 3. Failure Tests
- [√] F-SPAWN-01 → runtime creation failure returns `SpawnError` and leaves no member / lifecycle-owned TeamAgent
- [√] F-SPAWN-02 → wrapper、register、publication 或 commit failure reverse-cleans ownership；STARTING record uses `SPAWN_ROLLBACK`
- [√] F-MSG-01 → unknown target rejected with typed error and no enqueue
- [√] F-MSG-02 → mailbox full rejects without dropping queued messages
- [√] F-MSG-03 → unknown sender or STARTING / STOPPED / FAILED member rejected without state change
- [√] F-MSG-04 → empty、non-string and over 16,384-character content rejected
- [√] F-STATE-01 → test_invalid_member_transition_rejected_without_state_change
- [√] F-TASK-01 → 同一任务重复或并发领取产生明确冲突且仅一个 owner 成功
- [√] F-TASK-02 → 领取已提交但 BUSY 转换失败，返回真实状态，原 owner 可显式续跑
- [√] F-TASK-03 → 执行异常或一轮未完成，保持 `in_progress` / BUSY 并允许原 owner 续跑
- [√] F-TASK-04 → 完成已提交但 IDLE 转换失败，续跑仅修复成员状态
- [√] F-TASK-05 → 非 owner、跨团队成员及同成员重入被拒绝且目标状态不变
- [√] F-STOP-01 → 活动同步 turn 拒绝停止，不虚报 STOPPED，原 owner 仍可续跑
- [√] F-STOP-02 → 未完成任务或待恢复成员收尾拒绝停止；正常退出保留会话
- [√] F-STOP-03 → teardown 逐成员汇总失败，未清理完不得最终释放，可重试
- [√] F-STOP-04 → 明确 fatal 保留 FAILED / 错误与任务事实，普通执行异常不误判
- [√] F-STOP-05 → FAILED 任务显式恢复的 spawn / 交接前失败保留旧 owner；交接后失败保留新 owner 与续跑入口


# 4. 测试项目

# 4.1 架构测试
- [√] ARCH-01:
team/registry.py 不允许 import RuntimeFactory

- [√] ARCH-02:
TeamAgent communication 必须经过 MailboxHandle / MessageBus boundary，
禁止直接访问其他 Agent 或 mailbox storage。


- [√] ARCH-03:
TeamAgent AgentRuntime creation 入口必须经过 LifecycleManager；Coordinator、TeamAgent 与 team tool 不得调用 RuntimeFactory

- [√] ARCH-04:
全部 TeamAgent 使用既有 AgentRuntime；`TeamAgent.run(prompt)` 默认进入既有 `query_loop`

- [√] ARCH-05:
TeamRuntime 是独立的 team composition root，不并入 AgentRuntime；team-scoped shared services 由 TeamRuntime 组装并持有。

- [√] ARCH-06:
Team task 集成必须复用现有 task_system 的 TaskStore / task behavior，不得定义第二套 task model 或引入 Scheduler。

- [√] ARCH-07: AST 守卫 Registry 对 RuntimeFactory 的依赖、TeamAgent runtime 的 LifecycleManager 单一创建入口、统一 query_loop 及 TeamAgent 不直接访问 Bus mailbox storage；现有行为测试继续验证边界。
- [√] ARCH-08: Team 路径不引入 worktree、Scheduler、TeamAgent 自主领取或 idle/token-cost 自动淘汰；在限定模块范围核对语法与执行能力。

# 4.2 Contract / Isolation 测试
- [√] MSG-01 两个已发布 TeamAgent 经各自 handle 和专属工具收发；空队列返回 `None`，FIFO 顺序正确
- [√] MSG-02 两个 TeamRuntime 的 mailbox 与成员查询隔离，并发发送不丢失消息
- [√] MSG-03 消息操作不启动 TeamAgent `run()` / `query_loop`，不触发 MemberRegistry transition
- [√] MSG-TOOL-01 消息工具只在 TeamAgent policy；handler 验证 `ToolContext.runtime` 属于当前 wrapper，不能伪造 sender
- [√] STORE-01 两个 TeamRuntime 使用不同 TaskStore，写入与读取互不污染
- [√] STORE-02 未显式注入 store 的现有工具路径继续使用全局 `TASKS`，原有行为保持兼容
- [√] REGISTRY-01 所有 MemberState transition 均经过 MemberRegistry 的受控入口
- [√] REGISTRY-02 `unregister` 仅可用于 spawn 发布前 rollback 或 TeamRuntime 最终释放
- [√] SPAWN-01 Master tool → TeamCoordinator → LifecycleManager → RuntimeFactory → MemberRegistry 的整链 fake-runtime 测试返回 IDLE member
- [√] MASTER-TOOL-01 `spawn_teammate` 只通过 per-instance binding 暴露给 Master，不进入通用 / Subagent / TeamAgent tool set
- [√] COLLAB-01 Master 团队创建/看板/详情/分配 → 同步 TeamAgent turn → 完成任务并返回 IDLE；分配不写 mailbox
- [√] COLLAB-02 TeamAgent 团队任务工具验证实际 runtime / owner，工作区编辑与命令工具可路由，无自主领取
- [√] COLLAB-03 同一 TaskStore 并发领取恰有一个成功；旧全局任务工具仍兼容
- [√] COLLAB-04 执行异常、未完成和部分成功后，原 owner 的显式续跑与状态修复正确
- [√] COLLAB-05 任务不存在、依赖未完成、目标成员不可用、跨 TeamRuntime 与重复完成均被拒绝
- [√] COLLAB-06 同一成员执行期间不能重入；不同成员的任务状态仍按各自 owner 维护
- [√] COLLAB-07 TeamAgent 的 bash 仅前台执行，不能启动或接收其他 runtime 的全局后台命令结果
- [√] COLLAB-08 Master/TeamAgent 创建工具对非字符串任务主题和描述返回可预期错误，不中断 loop

- [√] STOP-01 Master 专属停止工具 → Coordinator → LifecycleManager → Registry；IDLE 成员停止后 record 为 STOPPED、wrapper 不可执行，重复停止幂等
- [√] STOP-02 活动同步 turn 的停止被拒绝；未完成或收尾未恢复任务保留原 owner / wrapper，显式续跑或修复后可停止
- [√] STOP-03 正常 `q/exit` 遇未完成任务或 teardown 失败时报告并保留会话；恢复后可退出
- [√] STOP-04 普通执行异常与显式 fatal 区分；fatal 保留 FAILED record、错误摘要与任务事实
- [√] STOP-05 teardown best-effort 汇总、部分失败重试、终态 record 保留与全部安全停止后的 `TEAM_RELEASE`；session TaskStore 文件保留
- [√] STOP-06 并发 send/receive 与 shutdown/fatal 有共同顺序边界，终态后拒绝收发、此前已接受消息保留至最终释放且无死锁
- [√] STOP-07 生命周期工具仅 Master 可用，跨 TeamRuntime member/session 与最终释放后的操作被拒绝
- [√] STOP-08 Master 对 FAILED 的 `in_progress` 任务逐项创建全新 TeamAgent 并立即执行；原 FAILED record 与现有 IDLE 成员上下文保持不变，完成后 teardown 可释放
- [√] STOP-09 交接记录兼容旧任务文件并持久保存；重复/并发恢复只有一个成功，spawn / 文件写入 / 成员转换失败分别保持正确 owner 与续跑入口
- [√] STOP-10 新成员未完成可续跑、再次 FAILED 可再次显式恢复；普通执行异常和非本团队任务不得通过恢复入口改派

# 4.3 成功标准
`doc\features\agent team\01_problem.md` 中的 `# 4. Success Criteria`

# 4.4 Phase 6 集成验证

- [√] INTEG-01 Master bound handler 创建两个 TeamAgent，经各自消息工具收发，创建与分配任务，由 fake loop 完成，再安全 teardown；核对 session、独立 runtime、任务 owner、消息边界与最终释放。
- [√] INTEG-02 任务 owner 持有 `in_progress` 后显式 fatal，首次 teardown 报告部分失败；Master 为该任务创建全新成员恢复完成，旧 FAILED record 保留至最终释放，交接与任务事实不丢失。

# 4.5 可选真实模型 E2E smoke

- [√] SMOKE-01 显式运行本地真实模型 smoke：Master bound 工具创建一名 TeamAgent 和一项任务，TeamAgent 经统一 query_loop 触发 `complete_team_task`；核对至少一次真实模型响应、实际 owner、任务 `completed`、成员 IDLE 与 teardown 最终释放。服务、协议、工具调用或释放失败须记录真实结果，不把跳过计为通过。验收证据见 TASK-08 [完成报告](_history/TASK-08_completion.md)与[已接受审阅](_history/TASK-08_completion-review.md)。

# 4.6 可选扩展真实模型运行验收

- [√] LIVE-01 Master bound 工具创建两名独立 TeamAgent 与各自任务；真实模型驱动发送、接收和两次完成工具；发送内容、接收的 sender / target / content、owner、任务完成、成员 IDLE 与最终释放全部正确。
- [√] LIVE-02 受控首轮未完成后任务为 `in_progress`、原 owner 为 BUSY；停止与首次 teardown 拒绝、其他成员不能续跑；原 owner 恢复工具后由真实模型完成任务，最终释放。
- [√] LIVE-03 受控未完成任务的 owner 被显式报告 fatal 后，首次 teardown 部分失败；恢复入口创建全新成员，由真实模型完成原任务；校验交接记录、旧 FAILED record、新 owner / IDLE 与最终释放。

交互式 Master 体验检查：在临时目录中以相同本地模型启动 `main.py`，观察模型自行选择 spawn / create / assign / get 工具及 `q` 退出。单独记录实际结果，不替代或阻塞 `LIVE-01～03`。



# 5. Traceability Matrix
|state| Requirement | Architecture | Contract | Failure | ADR | Test | Task |
|---|---|---|---|---|---|---|---|
| [√] | SC-01 spawn | architecture 1.1/2.1/2.4/2.5 | contract 2.4/2.5/3.1/3.3 | F-SPAWN-01/02 | ADR-001/002/007/008/010 | STATE-01/REGISTRY-02/SPAWN-01/MASTER-TOOL-01 | TASK-03 |
| [√] | SC-02 统一 AgentRuntime / query_loop | architecture 1.1/2.2 | contract 2.6/3.1/3.3 | F-TASK-02/03/04 | ADR-007/009/012 | ARCH-04、COLLAB-01/04 | TASK-03 / TASK-05 |
| [√] | SC-03 messaging | architecture 2.3 | contract 2.1/2.3/2.6 | F-MSG-01/02/03/04 | ADR-004/006/011 | ARCH-02、MSG-01/02/03、MSG-TOOL-01 | TASK-04 |
| [√] | SC-04 lifecycle entry | architecture 2.4/2.5 | contract 2.4/2.5/3.1/3.3 | F-SPAWN-01/02、F-STOP-01～05、F-STATE-01 | ADR-002/005/010/013/014/015 | STATE-03/04/06/07、ARCH-03、REGISTRY-01/02、STOP-01～05/07～10 | TASK-03 / TASK-06 |
| [√] | SC-05 no cross-module state mutation | architecture 2.3/2.5 | contract 2.2/2.3/2.5 | F-MSG-01/02/03、F-STATE-01、F-TASK-05、F-STOP-02/03/05 | ADR-002/003/004/011/012/013/014/015 | ARCH-02/06、STORE-01/02、REGISTRY-01、MSG-03、COLLAB-02/03/05/06、STOP-02/05/06/08/09 | TASK-04 / TASK-05 / TASK-06 |
| [√] | SC-06 happy path 与主要 failure path 的 Phase 6 增量验收 | architecture 2.1～2.6 | contract 2.1～3.3 | F-SPAWN-01/02、F-MSG-01～04、F-STATE-01、F-TASK-01～05、F-STOP-01～05 | ADR-007/011/012/013/014/015 | 既有 Failure/State/STOP 检查、INTEG-01/02 | TASK-07 |
| [√] | SC-07 Non-goal 的 Phase 6 增量验收 | architecture 2.1/2.2/2.6 | contract 2.2/2.6 | — | ADR-003/005/006/012 | ARCH-07/08、COLLAB-02、MSG-03 | TASK-07 |
| [√] | SC-02/04/06 的可选真实模型增量验证；不改变已接受的 MVP 状态 | architecture 1.1/2.2/2.4/2.5 | contract 2.4/2.6/3.1/3.3 | F-TASK-03/04、F-STOP-02/03 | ADR-007/008/010/012/013/014 | SMOKE-01 | TASK-08 |
| [√] | SC-01～06 的可选扩展真实模型增量验证；不改变已接受的 MVP 状态 | architecture 2.1～2.6 | contract 2.1～3.3 | F-TASK-03、F-STOP-02/03/05 | ADR-004/007/012/013/014/015 | LIVE-01～03 | TASK-09 |

