# TASK-05 Preflight Brief

Status: Archived / Non-authoritative

Task: TASK-05 Task Collaboration

Baseline: `0af6ca6567b7aab9a31e6f4391e98a181efdce95` (`feature/team`)

Outcome: 预检完成；DD-01～DD-05 待设计审阅，实施暂缓

Source of Truth: `../01_problem.md`～`../08_tasks.md`；本报告只记录现状与待裁决提案

## Preflight Verdict

**Ready for design review; blocked for implementation.** Phase 4 要连接 Master 的任务看板、显式分配、TeamAgent 的单次执行与 team-scoped TaskStore。现有规格确定组件所有权和禁止自主取任务，但尚未确定分配如何触发执行、任务 owner 身份、工具边界、并发领取及失败补偿；这些选择影响状态一致性，须先审阅。

## Baseline 与已验证事实

- 预检起点为上述 HEAD，开始时工作区无改动。TASK-04 状态更新与本报告是本轮未提交的文档变更，不构成新的代码提交；TASK-04 实现仍由 `0fbbbc3` 定位。
- 本轮执行 `uv run python -m pytest -q`：`293 passed in 2.31s`；`git show --check --oneline 0fbbbc3`、`git show --check --oneline b007aa4` 与起点 `git diff --check` 均 exit 0。该结果是 Phase 4 预检基线，不证明任务协作已实现。
- `TeamRuntime` 构造独立 TaskStore 并交给 Coordinator；Master session 使用 `.agents/runs/<session_id>/tasks` 路径：`0af6ca6/team/runtime.py:29`、`:40`，`0af6ca6/core/agent.py:124`～`:127`。
- 现有 task-system operation 可显式传入 `store`，未传入时回落全局 `TASKS`；通用 `run_*task` handler 仍使用默认全局路径：`0af6ca6/tools/task_system.py:247`～`:251`、`:449`～`:555`。已有 STORE-01 / STORE-02 测试证明隔离与兼容基础。
- `TeamCoordinator` 当前仅有 `spawn_teammate()`；Master team tool 也仅有 `spawn_teammate`：`0af6ca6/team/coordinator.py:32`、`0af6ca6/tools/team.py:11`～`:43`。尚无 Master 从团队看板读取或分配任务的绑定入口。
- `claim_task()` / `complete_task()` 通过文件读取、修改、保存任务，并以字符串返回成功或冲突；通用 handler 使用 `context.runtime.agent_name` 作为 owner：`0af6ca6/tools/task_system.py:367`～`:435`、`:525`～`:555`。当前路径没有覆盖同一任务并发领取的原子性承诺，也没有团队专属 typed conflict。
- `LifecycleManager.get_agent()` 可查询已发布 wrapper，`TeamAgent.run(prompt)` 可进入既有 query loop；消息收发不会自动调用该入口：`0af6ca6/team/lifecycle.py:111`、`0af6ca6/team/agent.py:36`、`0af6ca6/team/messaging.py:59`～`:75`。
- `MemberRegistry` 是 MemberState 的唯一 owner；`TASK_CLAIMED`、`TASK_FINISHED` 等事件已有受控 transition 与授权来源：`0af6ca6/team/registry.py:20`～`:64`、`:138`。

## 拟修改范围（仅在设计接受后）

- `team/coordinator.py`、`tools/team.py`：Master 的团队任务查询与显式分配 use case；只通过 TeamRuntime 已持有的服务取数和调用生命周期入口。
- `team/lifecycle.py`、`team/agent.py` 及专属工具绑定：被分配 TeamAgent 的显式执行入口与必要的任务工具；继续复用 AgentRuntime / query_loop，不建立 worker loop 或 Scheduler。
- `tools/task_system.py`：在现有 TaskStore / operation 中提供团队路径所需的冲突与 owner 语义，同时保留既有全局工具返回和路径兼容；必要时增加最小并发保护，不复制任务模型。
- `tests/team/*` 与相应任务工具测试：覆盖主链、隔离、失败和回归；接受的裁决再传播到 02～07、ADR、08。

## Design Deltas 待审阅

### DD-01：任务 owner 与成员身份

现有通用任务工具以显示名称作为 owner；Registry / LifecycleManager 则以实际 `agent_id` 识别成员。**建议：**Team 路径以实际 `agent_id` 保存 task owner；Master 指定目标 ID，Coordinator 验证该 ID 属于当前 TeamRuntime 且处于可接任务状态。看板、领取和完成都显式使用该 TeamRuntime 的 TaskStore；通用全局工具继续保留原行为。

### DD-02：分配与执行触发

目前 spawn 与消息均不启动执行，而 `03_runtime.md` 把 `task_claimed` 后的成员设为 BUSY。**建议：**Master 的一次显式 `assign_team_task` use case 完成校验、领取、受控状态转换，并同步触发目标 TeamAgent 的一次 `run(prompt)`；返回该次执行结果或明确失败。此提案不引入后台 worker，也不把 ADR-006 的消息触发语义提前用于任务执行。需裁决工具调用是否允许等待该单次执行，以及执行返回但任务未完成时 task/member 的状态。

### DD-03：团队任务工具权限

通用 `list_tasks/get_task/claim_task/complete_task` 指向全局 store，不能直接暴露给 Team 路径。**建议：**Master 专属工具提供团队看板读取、详情与显式分配；TeamAgent 专属工具提供团队任务详情、创建/更新和完成，全部绑定同一 TeamRuntime TaskStore。TeamAgent 不获得自主 claim；完成操作使用当前 runtime 的实际 `agent_id`，不接受调用者伪造 owner。需裁决最小工具清单和返回格式。

### DD-04：领取冲突与原子性

现有 `claim_task` 为无锁文件 read-modify-write，两个并发领取者可能同时成功；F-TASK-01 只写了 conflict/retry/read。**建议：**在现有 task-system 所有权内增加团队路径可用的 typed claim 结果或错误，并在单进程同一 TaskStore 内序列化领取；通用字符串 API 以薄适配维持兼容。跨进程文件锁、持久事务和分布式调度不纳入本阶段。需裁决失败时的可观察结果及锁覆盖范围。

### DD-05：部分成功与执行失败

领取任务、Registry 转 BUSY、运行 query loop、完成任务是跨模块步骤，现无统一补偿入口。**建议：**将“领取前校验失败”“领取成功但状态转换失败”“执行抛错”“执行结束但任务未完成”“重复完成”分开定义；任何失败均不得报告虚假完成或悄悄把任务改回 pending。明确由 Coordinator 记录和呈现可恢复状态，并把真正的 fatal runtime supervision 留给 Phase 5。需裁决哪些步骤可补偿、哪些保留 IN_PROGRESS / BUSY 供人工或后续生命周期处理。

## 验证计划与边界

- 用 fake runtime / fake loop 验证 Master 团队看板 → 指定 `agent_id` 分配 → TaskStore 领取 → Registry BUSY → TeamAgent 单次执行 → 完成与回到 IDLE 的路径；真实模型不是必需条件。
- 覆盖任务不存在、依赖未完成、重复/并发领取、跨 TeamRuntime task/member ID、非 IDLE 目标、伪造 runtime/owner、完成者不匹配，以及执行或工具失败时的任务与成员状态。
- 现有 STORE-01/02、REGISTRY-01/02、ARCH-04/06、SPAWN-01、MSG-01～03 和全量回归继续通过。范围检查确认没有自主取任务、Scheduler、后台执行、shutdown / teardown、worktree 或真实模型 smoke。

## 下一门槛

在 [`../Human_Review.md`](../Human_Review.md) 逐项接受、修改或拒绝 DD-01～DD-05 后，才把接受内容传播到权威规格、测试追踪和 TASK-05；随后进入实现。本报告的建议不等于已接受设计。
