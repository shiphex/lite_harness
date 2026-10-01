# TASK-07 Preflight Brief

Status: Archived / Non-authoritative

Task: TASK-07 Integration / Architecture Enforcement

Baseline: `eb9ed3b43388855f82226a525c2d324799d84883` (`feature/team`)，预检开始时暂存区与工作区均无改动

Outcome: Ready for design review；DD-01～DD-03 待人工裁决，Phase 6 尚未完成

Source of Truth: [`../01_problem.md`](../01_problem.md)～[`../08_tasks.md`](../08_tasks.md)；本报告只记录基线、证据、缺口与待审建议

## Preflight Verdict

**Ready for design review; blocked for implementation.** Phase 0～5 已完成验收，现有 336 项测试在本基线通过；这些结果证明既有阶段回归通过，不代替 Phase 6 的跨链路验收。TASK-07 需要明确全链路验证、架构约束守卫和 SC-06/07 的追踪方式。设计裁决被接受前，不实施依赖它们的测试或代码，也不勾选 Phase 6。

## 基线与证据

- `git status --short --branch` 显示 `feature/team...origin/feature/team`，无暂存或未暂存改动；HEAD 为上述提交。TASK-06 完成验收见 [`TASK-06_completion-review.md`](TASK-06_completion-review.md)，当前 [`../Human_Review.md`](../Human_Review.md) 保存其简要结论，正式历史审阅已归档，无需重复归档。
- `.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider` → **336 passed in 3.63s**。这是 TASK-07 预检的回归基线；未运行真实模型。
- Master session 创建 sibling TeamRuntime 并绑定团队工具：`eb9ed3b/core/agent.py:124`～`:137`。TeamRuntime 组装独立 Registry、Bus、TaskStore、LifecycleManager 与 Coordinator：`eb9ed3b/team/runtime.py:27`～`:42`。
- LifecycleManager 创建 TeamAgent runtime/wrapper 并持有生命周期，TeamAgent `run()` 使用统一 loop：`eb9ed3b/team/lifecycle.py:87`～`:135`、`:344`，`eb9ed3b/team/agent.py:30`～`:58`。消息工具通过 runtime 身份验证与绑定 handle 收发：`eb9ed3b/team/messaging_tools.py:39`～`:70`。
- Coordinator 使用同一 team store 分配、续跑和显式恢复；现有任务系统保留显式 store 注入及全局 `TASKS` 默认路径：`eb9ed3b/team/coordinator.py:73`～`:109`、`:138`～`:184`，`eb9ed3b/tools/task_system.py:296`～`:303`、`:441`～`:459`。
- 停止、fatal 和 teardown 经 LifecycleManager；消息与终态转换使用共同顺序边界：`eb9ed3b/team/lifecycle.py:156`～`:282`，`eb9ed3b/team/messaging.py:81`～`:92`。现有测试分别验证对应垂直链路、隔离和失败恢复。

## 需求与现有测试映射

现行 [`../01_problem.md`](../01_problem.md) §4 的 SC-01～07 均已在前序完成审阅中勾选；[`../07_test_plan.md`](../07_test_plan.md) §2～4 的既有检查项也已勾选。下表只核对当前基线的证据，不改动已有验收状态。

| 目标 | 当前证据 | Phase 6 待补强处 |
| --- | --- | --- |
| SC-01、SC-02：创建并使用统一 loop | `tests/tools/test_team.py`、`tests/team/test_lifecycle.py`、`tests/team/test_team_agent.py`；ARCH-03/04、SPAWN-01 | 将创建与后续协作纳入同一全链路场景 |
| SC-03：团队通信边界 | `tests/team/test_messaging.py`、`tests/team/test_messaging_integration.py`；ARCH-02、MSG-01～03、MSG-TOOL-01 | 与任务执行和释放串接验证 |
| SC-04：统一生命周期入口 | `tests/team/test_lifecycle.py`、`tests/team/test_shutdown.py`；ARCH-03、STATE/STOP 检查 | 在全链路场景核对停止、FAILED 与最终释放 |
| SC-05：模块状态所有权 | `tests/team/test_runtime.py`、`tests/team/test_registry.py`、`tests/team/test_task_collaboration.py`；ARCH-02/05/06、STORE/REGISTRY/COLLAB 检查 | 用结构守卫补强禁止跨边界直接调用的证据 |
| SC-06：happy path 与主要失败路径 | 已有 F-SPAWN、F-MSG、F-STATE、F-TASK、F-STOP 对应自动测试；全量回归通过 | `07_test_plan.md` §5 尚无 SC-06 追踪行；缺少串接全链路的成功与 fatal 恢复用例 |
| SC-07：不引入 Non-goal | `tests/team/test_architecture.py` 检查特定 scheduler/worktree 文件，`tests/team/test_task_collaboration.py` 检查无自主 claim；代码未见 idle/budget eviction 路径 | `07_test_plan.md` §5 尚无 SC-07 追踪行；现有文件名检查不覆盖所有引入方式 |

| 架构项 | 当前证据与限制 |
| --- | --- |
| ARCH-01 | `tests/team/test_architecture.py:7` 检查 Registry 中的字符串；可证明当前文本不含指定片段，但不是语法级 import 守卫 |
| ARCH-02 | `tests/team/test_messaging_integration.py:43`～`:139` 验证 handle、工具身份和无自动执行；未独立扫描 TeamAgent 对 Bus 存储的直接访问 |
| ARCH-03 | `tests/team/test_architecture.py:18` 与 `tests/team/test_lifecycle.py` 验证创建入口；静态部分依赖调用字符串 |
| ARCH-04 | `tests/team/test_architecture.py:34` 与 `tests/team/test_team_agent.py` 验证既有 loop；静态部分依赖 import 字符串 |
| ARCH-05 | `tests/team/test_runtime.py` 验证组合实例、独立性与双团队隔离 |
| ARCH-06 | `tests/team/test_runtime.py`、`tests/team/test_task_collaboration.py`、`tests/tools/test_task_system.py` 验证 TaskStore 复用和兼容；`test_architecture.py:13` 仅检查两个特定模块名 |

Failure Policy 的当前自动测试分布：F-SPAWN-01/02 在 `tests/team/test_lifecycle.py`；F-MSG-01～04 在 `tests/team/test_messaging.py`；F-STATE-01 在 `tests/team/test_registry.py`；F-TASK-01～05 在 `tests/team/test_task_collaboration.py`；F-STOP-01～05 在 `tests/team/test_shutdown.py` 与 `tests/core/test_agent.py`。这些测试已由前序阶段接受；TASK-07 要验证跨模块组合后的成功与失败路径，不能将原有勾选项重新解释为 Phase 6 已通过。

## 拟议修改范围（设计接受后）

- 在 `tests/team/` 增加无真实模型的全链路成功及 fatal 恢复场景，复用现有 fake runtime/loop、Master bound handler 与团队工具；避免复制生产业务逻辑。
- 在 `tests/team/test_architecture.py` 将适合语法判断的字符串检查改为针对性的 AST import/call 守卫；保留现有运行时契约测试作为状态所有权和隔离证据。若检查揭示真实契约违背，按发现项单独修复并验证，不预设产品 API 变更。
- 设计接受后才补充 `07_test_plan.md` 的新检查项与 SC-06/07 追踪行；按证据更新 `08_tasks.md`。真实模型 smoke 在 Phase 6 后可选，不作为 MVP 门槛。

## Design Deltas 待审阅

### DD-01：全链路验收场景

**建议接受。** 增加两类自动测试：其一由 Master bound handler 创建至少两个 TeamAgent，经 TeamAgent 专属工具通信，创建并分配团队任务，由 fake loop 完成，再安全 teardown；核对同一 session、独立 runtime/identity、任务 owner、消息边界与最终释放。其二使 owner 持有 `in_progress` 任务后显式报告 fatal，确认首次 teardown 返回部分失败，Master 为该任务创建全新成员并恢复完成，旧 FAILED record 留到最终释放。测试使用临时目录和 fake loop，不调用真实模型；不改变现有运行时 API 或自动调度语义。

### DD-02：架构边界守卫

**建议接受。** 对可语法判断的边界使用 Python AST 检查 import 与构造调用：Registry 不导入 RuntimeFactory；TeamAgent runtime 的工厂创建只出现在 LifecycleManager，Coordinator、TeamAgent 与团队工具不得自行创建；TeamAgent 不定义第二套 Runtime/loop，且不直接访问 MessageBus mailbox 存储。AST 检查聚焦现有模块与明确禁止的调用，避免依赖空格、注释或别名造成的简单字符串误判；ARCH-02/04/05/06 的动态身份、隔离和行为测试继续保留。Non-goal 守卫同时核对无 worktree/scheduler 能力、无 TeamAgent 自主领取与 idle/budget 自动淘汰。此方案只增强检测，不将文件位置误写成架构不变量。

### DD-03：SC-06/07 追踪闭环

**建议接受。** 在设计传播时为 `07_test_plan.md` §5 增加 SC-06、SC-07 两行，关联现有失败/架构/协作检查项以及 DD-01/02 经接受后新增的测试 ID；新增的 Phase 6 检查项及追踪行初始为 `[ ]`，表示增量验收尚未完成，不推翻 `01_problem.md` 中既有的 SC-06/07 验收。明确“前序阶段已有覆盖”与“Phase 6 全量验收”两种证据，不修改已接受的旧勾选项。仅当实现、全量验证和完成审阅均通过后，才勾选新增项及 Phase 6。

## 验证计划与下一门槛

- 预检交付仅改动本报告、`../08_tasks.md` 与 `../Human_Review.md`；01～07 的已接受规格未改写。三份文档的相对链接、行尾空白和待审状态检查通过；`git diff --check` exit 0（仅有 Git 行尾转换提示）。
- 设计接受后，先使新增集成与架构测试能暴露目标缺口，再实施最小补强；分别运行相关 `tests/team`、全量 pytest、文档追踪与相对链接检查、`git diff --check`。
- 对照 01～07 的责任边界复核失败结果、无跨团队污染、无静默丢任务或消息，以及 `#3 Non-goal`。如出现新的产品行为取舍，先补设计审阅。
- 请在 [`../Human_Review.md`](../Human_Review.md) 对 DD-01～DD-03 逐项接受、修改或拒绝。当前 Ready 仅表示可以送审，不表示获得实施或完成验收。
