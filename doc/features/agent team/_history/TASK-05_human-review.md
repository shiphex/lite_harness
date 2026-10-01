# TASK-05 Design Review

Status: Accepted Review

Task: TASK-05 Task Collaboration

Based on: [TASK-05_preflight.md](TASK-05_preflight.md)

Result: 用户在本轮接受 DD-01～DD-05 的方案，并补充接受 Master 创建团队任务、TeamAgent 使用现有工作区编辑与命令工具。Phase 4 的实现与完成审阅仍未验收。

Superseded by: [02_architecture.md](../02_architecture.md)、[03_runtime.md](../03_runtime.md)、[04_contracts.md](../04_contracts.md)、[05_failures.md](../05_failures.md)、[06_decisions.md](../06_decisions.md)、[07_test_plan.md](../07_test_plan.md)、[08_tasks.md](../08_tasks.md)

## 审阅依据

- `01_problem.md` §2.1 要求 Master 从看板检索并分配任务、TeamAgent 独立执行且共享任务状态；§3 排除 TeamAgent 空闲时自主取任务。
- `02_architecture.md` §2.1～2.2、`04_contracts.md` §2.2 / §3.1～3.3 和 ADR-003 要求复用现有 TaskStore、显式 team store 注入及全局工具兼容；`03_runtime.md` §1.2～1.3 给出任务与成员状态路径。
- `0af6ca6` 中 TeamRuntime 已有独立 TaskStore，Coordinator / Master team tool 只有 spawn；通用任务 handler 使用全局 store，claim/complete 返回文本，缺少团队分配与执行绑定。
- TASK-04 已受托完成审阅，见 [TASK-04_completion-review.md](TASK-04_completion-review.md)。本轮预检基线 `uv run python -m pytest -q` 为 293 passed；它不证明 Phase 4 已实现。

## 已接受的设计裁决

| ID | 裁决 | 影响 |
| --- | --- | --- |
| DD-01 任务 owner 与身份 | 接受：Team 路径以实际 `agent_id` 为 owner；Coordinator 只接受本 TeamRuntime 中可接任务的 member，并对所有任务操作显式传入 team store。 | 现有全局工具仍沿用当前显示名称和默认 store。 |
| DD-02 分配与执行 | 接受：一次 Master 显式分配同步执行一个 TeamAgent turn：校验、领取、Registry 转 BUSY、调用既有 `TeamAgent.run(prompt)`，不启动后台 worker。 | 直接传入任务指令，不向 mailbox 重复通知。 |
| DD-03 工具权限 | 接受并补足入口：Master 专属团队创建/看板/详情/分配/续跑工具；TeamAgent 专属团队详情/创建/更新/完成工具，全部绑定 team store；TeamAgent 无自主 claim，完成者来自当前 runtime。 | TeamAgent 还可使用现有 `bash`、`write_file`、`edit_file`；成功结果采用 JSON。 |
| DD-04 冲突与原子性 | 接受：在现有 task_system 内提供 typed team claim 结果，并序列化同一进程、同一 TaskStore 的领取；通用字符串接口维持兼容。 | 不承诺跨进程原子性；重复或并发领取必须有可观察冲突。 |
| DD-05 部分成功 | 接受：领取或执行后不静默退回 pending；异常或一轮结束未完成时保留原 owner 与 `in_progress`、成员 BUSY。Master 只可让原 owner 显式续跑，并可重试可恢复的状态转换。 | 部分成功返回实际 task/member 状态；不可恢复冲突明确报错，fatal supervision 留给 Phase 5。 |

## 拟议实施与验收门槛

1. 将已接受 DD-01～DD-05 和补充裁决传播到相关 02～07、ADR、07 追踪矩阵及 `08_tasks.md`；新增测试与 Phase 4 保持未完成。
2. 用 fake runtime / fake loop 验证 team-scoped 看板、显式分配、单次执行、owner 与状态一致性、跨 team 隔离、冲突和失败路径；保留全量已勾选回归。
3. 完成报告及独立完成审阅接受前，不勾选 Phase 4、SC-02 或新增任务检查项。本次设计裁决由用户在会话中明确接受。
