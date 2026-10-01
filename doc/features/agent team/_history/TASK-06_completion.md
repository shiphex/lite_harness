# TASK-06 Completion Report

Status: Archived / Non-authoritative

Task: TASK-06 Shutdown / Teardown / Failure Closure

Baseline: `506e185a33e2c9346e30a166f0b7aa3b03ec99dd` (`feature/team`); 本报告所述实现仍在未提交工作区

Outcome: 已实现并验证 Phase-5 停止、teardown、fatal、正常退出与 FAILED 任务新成员恢复路径；Phase 5 和新增检查项在完成审阅前保持未勾选

Source of Truth: [`../01_problem.md`](../01_problem.md)～[`../08_tasks.md`](../08_tasks.md)、[`../Human_Review.md`](../Human_Review.md)；设计接受记录见 [TASK-06_human-review.md](TASK-06_human-review.md) 与 [TASK-06_recovery-review.md](TASK-06_recovery-review.md)

## Actual changes

- Master 专属 `shutdown_teammate`、`teardown_team`、`report_team_fatal` 和 `get_team_member` 通过 TeamCoordinator 到 LifecycleManager；正常 `q/exit` 尝试 teardown，部分失败时报告原因并保留会话。
- LifecycleManager 统一管理活动同步 turn 的排他锁和 wrapper ownership。停止会拒绝活动执行、原 owner 的 `in_progress` 任务或待修复的成员状态；STOPPED / FAILED record 在最终释放前可查询。普通执行异常仍保留 Phase-4 续跑路径，显式 fatal 记录 FAILED 与错误摘要。
- Teardown 逐成员处理并汇总失败，保留部分成功后的 TeamRuntime 供重试。所有成员安全进入终态后才批量移除 Registry record、清空 mailbox；清理失败时恢复已接受消息。TaskStore 文件不删除；最终释放后团队操作被拒绝，重复 teardown 返回同一结果。
- MessageBus 收发与 shutdown / fatal transition 共用锁定顺序；终态后的收发被拒绝，先前接受的消息保留到最终释放。
- Master 专属 `recover_failed_team_task(task_id)` 只接受本团队 FAILED owner 的 `in_progress` 任务。Coordinator 逐项创建全新 `recovery_<task_id>` 成员，TaskStore 原子写入新 owner 与顺序交接记录，然后在新成员排他执行区内同步运行一轮；原 FAILED record 保留，现有 IDLE 成员及上下文不参与。
- 交接前失败保留原 owner，并停止已发布但未接任务的新成员；交接后成员状态转换或执行失败保留新 owner，供 `resume_team_task` 或再次 FAILED 后重新恢复。TaskStore 兼容没有 `reassignments` 的旧文件；普通执行异常仍由原 owner 续跑。
- 已接受的 DD-01～DD-06、CR-02 已传播至 02～07 与 ADR-013～015，TASK-06 任务设计和测试追踪已补全；`team/lifecycle.py` 两处乱码字符串已修复。

## Verification evidence

- 新增 `tests/team/test_shutdown.py`，覆盖停止幂等、活动 turn、BUSY / WAITING 与未完成任务、已完成任务的成员收尾修复、teardown 部分失败与重试、registry/mailbox 清理失败回滚、fatal 与普通执行异常区分、成员查询、并发消息顺序、跨 session 和最终释放边界。
- 恢复测试覆盖新 ID 与独立 runtime/message history、既有 IDLE 上下文保持、完成后 teardown、旧文件兼容、多任务逐项恢复、pending/completed/可恢复 owner/非本团队 owner 拒绝、重复并发请求、spawn / 临时文件 / 替换写入 / 状态转换失败，以及新成员续跑与再次 FAILED 后恢复。
- `tests/core/test_agent.py` 增加正常退出在 teardown 失败时继续会话、成功后退出的测试，并更新 Master 工具集合断言。关键行为测试先以缺失接口或错误行为失败，再实施代码。
- `.venv/Scripts/python.exe -B -m pytest tests/team/test_shutdown.py -q -p no:cacheprovider` → **26 passed**；`.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider` → **336 passed in 3.71s**。
- 现有 `__pycache__` 写入权限导致默认 `compileall` 报 `PermissionError`；设置 `PYTHONPYCACHEPREFIX` 至系统临时目录后，`.venv/Scripts/python.exe -m compileall -q team tools/team.py core/agent.py tests/team/test_shutdown.py tests/core/test_agent.py` → exit 0。
- `git diff --check` → exit 0（仅 Git 行尾转换提示）；Markdown 相对链接检查覆盖 TASK-06 修改文档与历史报告 → 无缺失链接。

## Boundary and remaining risks

- FAILED 成员仍持有 `in_progress` 任务时，正常 teardown / `q/exit` 继续拒绝退出。Master 须逐项调用显式恢复工具，由新成员完成或续跑任务；没有自动扫描、自动改派或取消契约。交接只保证单进程内锁定与同目录文件替换，不承诺跨进程事务或运行进程崩溃后的自动重放。
- `q`、`exit` 和空输入均进入同一正常退出分支，先尝试 teardown，失败时保留会话；`EOFError` / `KeyboardInterrupt` 与进程被外部终止仍走现有顶层退出路径。无后台 worker 强制关闭、跨进程事务、持久 mailbox 或真实模型 smoke。
- 所有改动尚未提交；本报告引用工作区实测结果，不宣称完成审阅已通过。Phase 5、SC-04～07、新增 F-STOP / STOP 检查项及 Completed Tasks 保持未完成。

## Next gate

请在 [`../Human_Review.md`](../Human_Review.md) 审阅本报告和实现，确认 DD-01～DD-06 及 CR-02 的实际结果，并接受或指出修改。接受后再更新有证据的检查项、Phase 5 与完成任务记录；未有真实结束提交时不填写提交引用。
