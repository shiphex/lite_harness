# TASK-07 Design Review

Status: Accepted Review

Task: TASK-07 Integration / Architecture Enforcement

Based on: [TASK-07_preflight.md](TASK-07_preflight.md)

Result: 用户在本轮回复“接受”，DD-01～DD-03 全部通过设计审阅；允许按已接受范围实施 TASK-07，Phase 6 仍未完成

Superseded by: updated [`../07_test_plan.md`](../07_test_plan.md)、[`../08_tasks.md`](../08_tasks.md)；当前审阅入口见 [`../Human_Review.md`](../Human_Review.md)

Reviewer: 用户（本轮明确回复“接受”，覆盖 DD-01～DD-03）

Prepared by: Codex

Baseline: `eb9ed3b43388855f82226a525c2d324799d84883` (`feature/team`)

## 审阅依据

- TASK-06 / Phase 5 的已接受完成审阅已归档于 [TASK-06_completion-review.md](TASK-06_completion-review.md)。当前预检基线工作区干净，全量 pytest **336 passed in 3.63s**；该结果是既有阶段回归证据，不等于 Phase 6 验收。
- [01_problem.md](../01_problem.md) §4 的 SC-01～07 和 [07_test_plan.md](../07_test_plan.md) 的现有检查项已由前序阶段接受；`07_test_plan.md` §5 追踪矩阵只有 SC-01～05。当前架构测试对部分边界采用源码字符串检查，全链路行为由分散的垂直切片测试覆盖。
- 本次裁决只确定 Phase 6 的验证与追踪方案；不新增运行时能力、公开 API 或真实模型验收要求。详细代码与测试映射见[预检报告](TASK-07_preflight.md)。

## 设计差异与裁决

### DD-01：全链路成功与 fatal 恢复验证

**建议裁决：接受。** 用 fake runtime/loop，经 Master bound handler、两个 TeamAgent 的消息工具、团队任务分配与完成，验证从创建到安全 teardown 的同一条链；再验证未完成任务的 owner 显式 fatal、首次 teardown 部分失败、新成员显式恢复并完成、最终释放。两类测试均核对实际任务 owner、成员状态、隔离与失败结果，不调用真实模型。

**备选：**仅复用各阶段已通过的垂直切片测试。此方案成本较低，但不能单独证明这些入口在同一 TeamRuntime 中组合后仍正确。

**裁决：接受。** 按上述两类场景添加无真实模型的全链路验证。

### DD-02：针对性的 AST 架构守卫

**建议裁决：接受。** 将适合语法判断的 RuntimeFactory 导入、创建入口及第二套 runtime/loop 等字符串检查改为 AST import/call 检查；对 TeamAgent 直接访问 Bus mailbox 存储和 Non-goal 的引入做限定范围守卫。保留已有运行时测试验证身份、状态所有权、隔离与兼容性，不以静态检查代替行为证据。守卫只针对已接受的模块职责，不把文件位置误设为新架构约束。

**备选：**维持现有字符串检查，只增加全链路测试。此方案改动较少，但对注释、别名和调用写法敏感，也难以稳定阻止边界回退。

**裁决：接受。** 用针对性的 AST 守卫补强静态架构检查，保留运行时证据。

### DD-03：SC-06/07 追踪闭环

**建议裁决：接受。** 设计传播时在 `07_test_plan.md` §5 增加 SC-06、SC-07 追踪行，关联现有失败/架构测试与 DD-01/02 新增检查项。新增的 Phase 6 检查项与追踪行保持 `[ ]`，表示增量验收尚未完成，不推翻 `01_problem.md` 中既有的 SC-06/07 验收；仅在实现、验证及完成审阅通过后勾选新项与 Phase 6。

**备选：**只在完成报告中叙述覆盖关系。此方案不改矩阵，但 07 的追踪关系仍缺少两个已接受成功标准。

**裁决：接受。** 增加 SC-06/07 追踪行，新增 Phase 6 检查项维持未完成状态。

## 审阅结果与交接

DD-01～DD-03 已全部接受，传播到 `07_test_plan.md` 与 `08_tasks.md`。本轮裁决只涉及验证方案和追踪，不改变产品架构或公开契约，因此不新增 ADR。实施及验证后仍需独立完成审阅；接受前 Phase 6 与新增检查项保持未完成。真实模型 E2E smoke 在 Phase 6 后可选，不阻塞 MVP。
