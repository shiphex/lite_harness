# TASK-06 Completion Review

Status: Pending Human Review

Task: TASK-06 Shutdown / Teardown / Failure Closure

Based on: [_history/TASK-06_completion.md](_history/TASK-06_completion.md)

Result: 待人工审阅；Phase 5、SC-04～07 和新增 F-STOP / STOP 检查项仍未勾选。

Accepted design: [_history/TASK-06_human-review.md](_history/TASK-06_human-review.md)；CR-02 补充设计见 [_history/TASK-06_recovery-review.md](_history/TASK-06_recovery-review.md)

Prepared by: Codex

## 审阅依据

- 实现位于当前未提交工作区，基线 HEAD 为 `506e185a33e2c9346e30a166f0b7aa3b03ec99dd`。实际改动、失败路径、边界与风险见 [TASK-06 Completion Report](_history/TASK-06_completion.md)。
- 全量 `.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider` 为 336 passed；针对性停止/恢复测试 26 passed。临时缓存目录下的 `compileall`、`git diff --check` 和相对链接检查结果见完成报告。测试证据不代替人工完成审阅。
- 正常停止拒绝活动 turn、未完成任务和待修复成员状态；teardown 汇总逐成员与最终释放失败。正常 `q/exit` 遇部分失败保留会话。fatal 只由显式报告进入 FAILED，错误摘要与任务事实可查询。
- 用户已接受 CR-01 的停止/teardown 设计，并裁决 CR-02：Master 显式指定 FAILED 成员的某项未完成任务时，创建全新 TeamAgent 接手并立即执行一轮，现有 IDLE 成员保持原上下文。实现与失败路径证据见完成报告；本页只等待完成审阅。

## 待审阅事项

| ID | 核对内容 | 待裁决点 |
| --- | --- | --- |
| CR-01 | 用户已接受原停止/teardown 设计；核对 DD-01～DD-06 的实现与回归证据。 | 如有实现缺口，指出具体修改。 |
| CR-02 | 用户已接受新 TeamAgent 恢复设计；核对 `recover_failed_team_task`、交接记录、失败回滚/续跑、独立上下文与任务完成后退出。 | 接受实际实现或指出具体修改。 |
| CR-03 | 完成审阅的记录步骤：核对 Phase 5、SC-04～07 与 F-STOP / STOP 检查项是否具备验收证据。 | 仅在代码与报告审阅接受后勾选；Completed Tasks 须引用真实结束提交。 |

## 拟议结果

待用户完成审阅回复。CR-01 和 CR-02 的设计裁决已接受；当前不把测试通过等同于任务验收，不勾选 Phase 5，也不填写不存在的提交引用。
