# TASK-05 Design Review

Status: Pending Human Review (Codex prepared; no design acceptance recorded)

Task: TASK-05 Task Collaboration

Based on: [_history/TASK-05_preflight.md](_history/TASK-05_preflight.md)

Result: 待裁决 DD-01～DD-05。以下均为预检建议，不是已接受设计；Phase 4、SC-02 和新增测试项保持未完成。

## 审阅依据

- `01_problem.md` §2.1 要求 Master 从看板检索并分配任务、TeamAgent 独立执行且共享任务状态；§3 排除 TeamAgent 空闲时自主取任务。
- `02_architecture.md` §2.1～2.2、`04_contracts.md` §2.2 / §3.1～3.3 和 ADR-003 要求复用现有 TaskStore、显式 team store 注入及全局工具兼容；`03_runtime.md` §1.2～1.3 给出任务与成员状态路径。
- `0af6ca6` 中 TeamRuntime 已有独立 TaskStore，Coordinator / Master team tool 只有 spawn；通用任务 handler 使用全局 store，claim/complete 返回文本，缺少团队分配与执行绑定。
- TASK-04 已受托完成审阅，见 [_history/TASK-04_completion-review.md](_history/TASK-04_completion-review.md)。本轮预检基线 `uv run python -m pytest -q` 为 293 passed；它不证明 Phase 4 已实现。

## 待裁决设计差异

| ID | Codex 建议裁决 | 需要确认的影响 |
| --- | --- | --- |
| DD-01 任务 owner 与身份 | Team 路径以实际 `agent_id` 为 owner；Coordinator 只接受本 TeamRuntime 中可接任务的 member，并对所有任务操作显式传入 team store。 | 现有全局工具仍沿用当前显示名称和默认 store，不将其解释为 Team 路径。 |
| DD-02 分配与执行 | 一次 Master 显式分配同步执行一个 TeamAgent turn：校验、领取、Registry 转 BUSY、调用既有 `TeamAgent.run(prompt)`，不启动后台 worker。 | Master 工具调用将等待该 turn；执行返回而任务未完成时的状态须与 DD-05 一并裁决。 |
| DD-03 工具权限 | Master 专属团队看板/详情/分配工具；TeamAgent 专属团队任务详情、创建/更新/完成工具，全部绑定 team store；TeamAgent 无自主 claim，完成者来自当前 runtime。 | 需确认最小工具清单与工具结果格式，避免误用全局 `TASKS`。 |
| DD-04 冲突与原子性 | 在现有 task_system 内提供 typed team claim 结果，并序列化同一进程、同一 TaskStore 的领取；通用字符串接口维持兼容。 | 不承诺跨进程原子性；重复或并发领取必须有可观察冲突。 |
| DD-05 部分成功 | 分别规定领取、成员 transition、执行、完成各步失败后的 task/member 状态；不报告虚假完成，不静默重置已领取任务。 | 确定可补偿步骤、失败后的可恢复入口，以及哪些 fatal 情况留给 Phase 5。 |

## 拟议实施与验收门槛

1. 仅在 DD-01～DD-05 获明确接受或修改裁决后，传播到相关 02～07、ADR、07 追踪矩阵及 `08_tasks.md`；新增测试与 Phase 4 保持未完成。
2. 用 fake runtime / fake loop 验证 team-scoped 看板、显式分配、单次执行、owner 与状态一致性、跨 team 隔离、冲突和失败路径；保留全量已勾选回归。
3. 完成报告及独立完成审阅接受前，不勾选 Phase 4、SC-02 或新增任务检查项。当前文件由 Codex 准备，尚无人工接受记录。
