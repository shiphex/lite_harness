# TASK-03 Preflight Brief

Status: Archived / Non-authoritative

Task: TASK-03 Spawn Vertical Slice

Baseline: `333e1e70ab14e592dc3d7cafa6d6aefcf644fbf6`

Working tree input: `../08_tasks.md` 中尚未提交的 TASK-03 task specification

Outcome: Human reviewed；DD-01～DD-04 已裁决，详见 [`TASK-03_human-review.md`](TASK-03_human-review.md)

Source of Truth: `../01_problem.md`～`../08_tasks.md`

---

## Preflight Verdict at Submission

**Blocked pending Human Review.** 技术上可行，基线测试通过；但当前 Spec 无法唯一确定 4 个关键接缝，需要先裁决下列 Design Deltas。

## Baseline

- Branch：`feature/team`
- HEAD：`333e1e70ab14e592dc3d7cafa6d6aefcf644fbf6`
- 工作区：仅 `../08_tasks.md` 有未提交修改；本次 Preflight 未修改文件。
- 已接受代码事实基线：`70825632e033e64778d5373d6d8da2b619a56ad8`
- Baseline tests：`uv run pytest -q` → `237 passed in 2.36s`
- `git diff --check`：通过，仅有 Git 的 LF→CRLF 提示。

## Confirmed Implementation Facts

- `TeamRuntime` 已组装 Registry、Lifecycle、Coordinator 等共享服务，但没有 Master binding：`333e1e7/team/runtime.py:14`。
- `TeamCoordinator`、`LifecycleManager` 目前只有依赖持有，没有 spawn 行为：`333e1e7/team/coordinator.py:10`、`333e1e7/team/lifecycle.py:8`。
- Registry 已支持 STARTING → IDLE、`SPAWN_ROLLBACK` 和 typed registry errors：`333e1e7/team/registry.py:138`。
- Master 使用全局 `TOOLS_LIST / TOOLS_HANDLERS`；普通 Subagent 只使用 STANDARD 集合，因此可以实现仅 Master 暴露 spawn：`333e1e7/core/agent.py:28`、`333e1e7/tools/subagent.py:67`。
- `RuntimeFactory.create()` 已提供 session、identity、workspace、events 和 interaction 注入，但会立即创建 runtime 路径：`333e1e7/core/runtime.py:143`。

## Planned Modules

- `team/*`：增加 TeamAgent execution wrapper、spawn contracts，并实现 LifecycleManager 与 Coordinator 的 spawn 链路。
- `tools/*`：增加 session-bound `spawn_teammate` definition/handler。
- `core/agent.py`：仅增加 Master/TeamRuntime composition seam，不修改 AgentRuntime 或 query_loop。
- 测试：增加 lifecycle、coordinator、TeamAgent、team tool 和 Master binding 测试，并保留全部 Phase 1 回归。

## Design Deltas Requiring Review

### TASK-03-DD-01：spawn 与执行时机

当前任务同时要求：

- spawn 最终发布 IDLE member；
- 创建并“启动”worker；
- 不实现 messaging、task assignment、fatal supervision 或 shutdown。

若 spawn 立即在后台执行初始 prompt，将缺少合法的 BUSY transition、结果通道、运行失败处理和清理入口。

**推荐裁决：**

- Phase 2 的 spawn 只创建并发布被动 `TeamAgent` execution wrapper，不启动后台线程、不立即调用模型。
- `TeamAgent.run(prompt)` 作为后续 Phase 使用的执行入口，内部只能进入现有 `query_loop`。
- ARCH-04 通过 fake-loop contract test 验证。
- 将 TASK-03 中“worker 创建/启动失败”收窄为“runtime、TeamAgent wrapper、registry 发布失败”。
- 异步 worker、输入触发、结果返回、fatal supervision 和 shutdown 留给后续 Phase。

### TASK-03-DD-02：Master 与 TeamRuntime 的持有方式

**推荐裁决：**

- `master_agent()` 生成一个 session ID，同时创建 TeamRuntime 和 Master AgentRuntime。
- TeamRuntime 使用 `.agents/runs/<session_id>/tasks` 作为 session-scoped TaskStore 路径。
- `create_master_runtime(...)` 增加可选的 TeamRuntime/session 参数，按实例绑定 team handler；原有无 TeamRuntime 调用保持兼容。
- `master_agent()` 的局部变量显式持有 TeamRuntime，bound handler 同时保持其生命周期。
- 不向 AgentRuntime 增加 `team` 字段，不合并两种 runtime 的状态。

### TASK-03-DD-03：TeamAgent 固定运行策略

**推荐裁决：**

- TeamAgent 与 Master 共享 `session_id`、workspace、model/fallback model 和 EventSink。
- TeamAgent 拥有独立 `agent_id`、state、history、runtime paths，使用 `NonInteractiveInteraction`。
- Memory 使用现有模型：`READ_ONLY`，读取 `master` namespace。
- Phase 2 只开放固定只读工具 `read_file`、`glob`、`load_skill`；不开放 spawn、Subagent、task、messaging 或写工具。
- `max_turns` 使用现有 Subagent 默认值 `30`，不新增配置项或 profile system。

### TASK-03-DD-04：API、发布顺序与 rollback

**推荐接口：**

- `TeamCoordinator.spawn_teammate(*, parent_runtime, agent_name) -> MemberRecord`
- `LifecycleManager.spawn(*, parent_runtime, agent_name) -> MemberRecord`
- `TeamAgent.run(prompt) -> tuple[state, status]`
- 新增 `SpawnError(TeamError)`，工具 handler 将 domain error 转为稳定文本结果。

**推荐顺序：**

1. 校验 `agent_name`，禁止空值和路径字符。
2. LifecycleManager 调用 RuntimeFactory。
3. 创建 TeamAgent wrapper。
4. Registry 注册 STARTING record。
5. LifecycleManager 保存 `agent_id → TeamAgent`。
6. Registry 应用 `SPAWN_SUCCESS`，发布 IDLE record。
7. Coordinator 将该 record 返回给 Master tool。

失败时逆序移除 LifecycleManager 引用，并对 STARTING record 使用 `SPAWN_ROLLBACK`。现有 AgentRuntime 没有 destroy/close contract，因此本阶段“无 leaked runtime”定义为没有可达的 runtime/TeamAgent 引用；不删除 RuntimeFactory 已创建的诊断目录。

## Verification Gate

Human 接受上述 DD 后，TASK-03 才可进入实现。完成标准为：

- happy path 完整经过 Master tool → Coordinator → Lifecycle → RuntimeFactory → Registry；
- spawn tool 只存在于实际 Master policy；
- member identity 与 AgentRuntime 一致，最终为 IDLE；
- TeamAgent execution wrapper 只调用现有 query_loop；
- runtime、register、wrapper publication、transition 各失败点均无残留 Registry/TeamAgent；
- F-SPAWN-01/02、ARCH-03/04 和全部既有测试通过；
- 不引入 Phase 3～5、worktree、Scheduler、profile 或真实模型依赖。
