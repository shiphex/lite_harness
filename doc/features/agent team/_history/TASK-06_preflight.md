# TASK-06 Preflight Brief

Status: Archived / Non-authoritative

Task: TASK-06 Shutdown / Teardown / Failure Closure

Baseline: `506e185a33e2c9346e30a166f0b7aa3b03ec99dd` (`feature/team`)

Outcome: 预检完成；DD-01～DD-06 待设计审阅，尚未授权实施

Source of Truth: `../01_problem.md`～`../08_tasks.md`；本报告仅记录基线、差异和待裁决提案

## Preflight Verdict

**Ready for design review; blocked for implementation.** 现行规格要求 Master 显式停止、team teardown、可观察终态、幂等与失败汇总，但没有定义正在同步执行的 TeamAgent 如何停止、未完成任务如何保留、最终释放的条件，以及消息与 shutdown 的并发顺序。DD-01～DD-06 接受前，不实施依赖这些取舍的代码。

## 基线与证据

- 预检起点是上述 HEAD；`git status --short --branch` 显示 `feature/team` 比远端领先 8 个提交，暂存区和工作区均无改动。TASK-05 的完成接受和归档已记录在 [`TASK-05_completion-review.md`](TASK-05_completion-review.md)，Phase 5 尚未勾选。
- 本轮执行 `.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider`：`309 passed in 4.65s`。这是进入 Phase 5 前的回归基线，不证明 shutdown / teardown 已实现。
- `LifecycleManager` 只实现 `spawn()`、`get_agent()` 与未发布对象的 rollback；`_agents` 保留已发布 wrapper，没有 shutdown / teardown：`506e185/team/lifecycle.py:57`～`:132`、`:195`～`:212`。`TeamRuntime` 只组装服务，没有 release 入口：`506e185/team/runtime.py:15`～`:43`。
- `MemberRegistry` 已有授权的 SHUTDOWN / FATAL_RUNTIME_ERROR 转换、STOPPED / FAILED 幂等转换及 `TEAM_RELEASE` unregister；这些只是状态基础，不代表生命周期流程完成：`506e185/team/registry.py:20`～`:55`、`:88`～`:115`、`:138`～`:176`。
- Master 仅绑定 spawn 和团队任务工具，CLI session 退出路径直接 `break`，没有统一 teardown：`506e185/tools/team.py:12`～`:65`、`:130`～`:137`，`506e185/core/agent.py:148`～`:157`。
- TeamCoordinator 用自身的成员执行锁同步运行一轮 TeamAgent；执行异常当前返回 `execution_error`，并保留 `in_progress` / BUSY 供原 owner 续跑：`506e185/team/coordinator.py:70`～`:84`、`:141`～`:164`。不能把所有普通执行异常自动解释为 fatal，否则会破坏 TASK-05 已接受的恢复语义。
- `MessageBus.send/receive` 在 bus 锁内读 Registry 状态，但 Registry transition 不取得 bus 锁；状态检查与队列操作相对 shutdown 尚无共同同步边界：`506e185/team/messaging.py:59`～`:74`、`506e185/team/registry.py:161`～`:176`。当前 bus 也没有 mailbox 清理入口。
- TeamAgent 复用现有 query loop，`AgentRuntime` 没有 `destroy()` / `close()` contract；Phase 2 已接受仅清理逻辑 ownership、允许保留 runtime 诊断目录：`506e185/team/agent.py:45`～`:58`、`04_contracts.md` §2.4、ADR-010。

## 需求与边界

- `01_problem.md` §2.1 / SC-04、SC-05 要求 Master 可显式 shutdown 与 team teardown，并由统一入口处理 TeamAgent 生命周期及跨模块状态所有权；§3 排除 idle timeout 和 token/cost eviction。
- `02_architecture.md` §2.3～2.6、`03_runtime.md` §1.2、`04_contracts.md` §2.4～2.5、ADR-002/005/010 要求 Registry 唯一持有状态，终态记录保留到 TeamRuntime 最终释放，LifecycleManager 持有 wrapper/runtime，消息归 MessageBus，任务归 TaskStore。
- `05_failures.md` 要求幂等、best-effort teardown、失败汇总、fatal 可观察；F-STOP-01 的“worker won't stop / force cleanup”与当前无后台 worker、无 runtime close contract 尚不一致，需要裁决。TASK-05 已接受的 F-TASK-03/04 要求普通执行异常和部分成功可续跑。
- 本任务不增加后台 worker、消息驱动执行、任务自动重分配、持久消息、跨进程事务、worktree、真实模型 smoke，也不删除诊断目录。

## 拟议修改范围（设计接受后）

- `team/lifecycle.py`、`team/coordinator.py`、`team/runtime.py`：停止、fatal 报告、best-effort teardown、最终释放与执行互斥的用例边界。
- `team/registry.py`、`team/messaging.py`、`team/contracts.py`：仅增加实现所需的受控同步/清理接口与 typed 错误或结果；保持各自状态所有权。
- `tools/team.py`、`core/agent.py`：Master 专属显式停止/teardown 工具，以及 session 退出时的收尾入口和可观察结果。
- `tests/team/*`、必要的 session 测试，以及设计接受后对应的 02～07、ADR、08 更新；所有现有勾选项继续作为回归条件。

## Design Deltas 待审阅

### DD-01：入口、身份和停止结果

**建议：**Master 专属 `shutdown_teammate(agent_id)` 委托 Coordinator → LifecycleManager，验证当前 TeamRuntime 的规范 `agent_id`；LifecycleManager 成为已发布 wrapper 停止与释放 ownership 的唯一入口，Registry 仍是唯一状态 owner。首次成功停止返回 STOPPED record；重复停止返回相同终态且不重复副作用；未知或跨 team ID 明确报错。停止后 `get_agent()` 不再提供可执行 wrapper，Registry record 仍可查。Master 专属 `teardown_team()` 走同一入口；成功 teardown 后拒绝 spawn、分配、消息和新任务操作。需裁决工具结果格式与 session 退出是否自动调用 teardown（建议调用并记录失败，不静默丢弃）。

### DD-02：同步执行中的停止与未完成任务

**建议：**把成员“当前正在 `run()`”与“BUSY 但本轮已结束、任务待续跑”分开。执行锁的排他权应由 LifecycleManager 提供给 Coordinator 使用；停止若遇到正在执行的一轮，应立即返回 typed `StopBusyError`，不伪称强制停止、不切换 Registry 状态，待该轮结束后可重试。若没有活动执行，即使 member 为 BUSY / WAITING，也可按已接受状态机转 STOPPED；原任务仍保持 `in_progress` / 原 owner，并在停止结果中列出未完成任务，不能报告任务完成或悄悄重分配。是否允许这种不可续跑的任务保留，须由用户裁决；备选是拒绝停止直至任务完成。

### DD-03：fatal 分类与可观察性

**建议：**保留 TASK-05 的普通 `execution_error` → BUSY / 原 owner 可续跑。仅明确不可恢复的 runtime 故障或监督入口显式报告 fatal 时，由 LifecycleManager 提交 `FATAL_RUNTIME_ERROR`，保留 FAILED record、错误摘要和未完成任务事实，释放可执行 wrapper；重复报告保持 FAILED。不能凭一次 query loop 异常自动标记 fatal。需要裁决最小的 fatal 报告入口及何种错误可归为不可恢复；本阶段用 fake runtime 注入验证，不承诺无法检测的进程崩溃自动上报。

### DD-04：teardown 与最终释放

**建议：**Coordinator 调用 LifecycleManager best-effort 停止每个成员并汇总逐成员结果；单个失败不跳过其他成员。存在 StopBusyError 或其他未清理故障时返回部分失败、保留 TeamRuntime 服务和 STOPPED / FAILED 记录，允许再次 teardown。所有成员已不再运行且逻辑 ownership 已清理后，TeamRuntime 才进入最终释放：通过 `TEAM_RELEASE` 移除 Registry record、清空内存 mailbox；TaskStore 的 session 文件不删除。重复 teardown 返回稳定完成结果。需裁决失败汇总与终态 record 在“停止完成到最终释放”之间的查询窗口。

### DD-05：shutdown 与消息的顺序

**建议：**给消息操作与 Registry 的停止/fatal transition 建立同一顺序边界；状态检查与入队/出队必须相对该 transition 原子排序。已在线性化点之前完成的消息可留在队列，之后的 send/receive 必须以 `MessageUnavailableError` 拒绝；停止时保留 mailbox 到 team 最终释放，避免悄悄丢弃已接受消息。保持 MessageBus 拥有队列、Registry 拥有状态，具体共享锁/受控 guard 由实现选择并用并发测试证明无死锁。此项不扩展为消息持久化或执行驱动。

### DD-06：F-STOP-01 的适配

**建议：**把 F-STOP-01 的“worker won't stop / force cleanup”改成当前同步架构可实现的语义：活动 turn 不可强制中断时返回 StopBusyError，状态与 ownership 不变；真正 fatal 走 DD-03 的 FAILED 路径；teardown 将两者分别汇总。不得仅为了符合旧措辞引入后台 worker 或虚构 runtime close。需裁决这是否满足本阶段的 failure closure，或是否要求额外的可取消 runtime contract（后者是新的架构取舍）。

## 验证计划

- fake runtime / fake loop 覆盖 IDLE、BUSY（无活动 turn）、WAITING、STOPPED、FAILED 的停止与重复停止；核对 Registry record、wrapper 可达性、任务 owner/status、工具权限与跨 team ID。
- 用阻塞 fake loop 确定性复现活动执行与停止/teardown 的竞态，确认不强制中断、不虚报成功，任务完成/异常路径仍维持 TASK-05 已接受行为。
- 并发 send/receive 与 shutdown/fatal，验证状态转换前后顺序、终态拒绝、已入队消息保留到最终释放及无死锁。
- 注入各成员停止失败、fatal 报告失败、清理失败，验证 best-effort 汇总、可重试、不提前 `TEAM_RELEASE`；验证退出路径可观察收尾结果。
- 运行针对性 `tests/team`、完整 pytest、compileall、`git diff --check`，核对 SC-04/05 与 F-STOP-01 的追踪关系；只有完成审阅接受后才勾选 Phase 5 或新检查项。

## 下一门槛

请在 [`../Human_Review.md`](../Human_Review.md) 对 DD-01～DD-06 逐项接受、修改或拒绝。接受前不将提案传播为权威规格，不实施依赖提案的代码；本报告的 Ready 仅表示可送审。
