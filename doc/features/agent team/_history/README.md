# Agent Team History

> Status: Archived / Non-authoritative

`_history/` 只保存能够解释 Agent Team 架构演进的 milestone evidence。这里的内容记录“历史上发生过什么”，不定义当前系统行为。

## Information Ownership

| 信息 | Source of Truth |
| --- | --- |
| 当前系统事实 / 当前计划 | [`../08_tasks.md`](../08_tasks.md) |
| 被接受的架构真相 | `../01_problem.md`～`../07_test_plan.md` 中对应的 authoritative location |
| 历史调查、报告和审阅过程 | 本目录、Git commit 或 PR |

如果历史内容与当前文档冲突，以 01～08 的当前内容为准。

## Admission Policy

只保存 milestone evidence：

- 正式 Gap Analysis 或同等级调查报告。
- 已完成的 Human Review。
- 能解释重大架构变化、且当前 Spec / ADR 无法完整表达调查过程的审阅记录。

以下内容不进入本目录：

- 中途建议、临时 brainstorm 或失败的 prompt 输出。
- 普通实现任务的测试输出；由 Git / CI 保存即可。
- 已进入 ADR 的最终决定副本；ADR 本身是 Source of Truth。

判断标准：半年以后，该材料是否仍能解释“为什么当前系统变成这样”，并且当前 Spec / ADR 是否无法完整解释其调查过程。

## Naming

文件名使用 `TASK-XX_<artifact>.md`，例如：

- `TASK-01_gap-analysis.md`
- `TASK-01_human-review.md`

## Evidence References

历史代码或文档证据使用以下形式：

```text
<baseline-commit>/<repo-relative-path>:<line>
```

例如：`f90561f/core/runtime.py:113`。当同一段已经明确唯一 baseline 时，也可以简写为 `core/runtime.py:113`。

- 不使用 `E:/...`、`C:/...` 等本机绝对路径。
- 历史 evidence 绑定调查当时的 baseline，不随 living document 的后续行号变化。
- 指向当前 authoritative contract 的引用继续使用 `path + §section`。
- History、Review 和 Source of Truth 之间的导航使用仓库相对链接；导航链接不作为历史 evidence。

## Required Metadata

正式报告必须包含：

```text
Status: Archived / Non-authoritative
Task: TASK-XX <name>
Baseline: <commit hash>
Outcome: <review state>
Source of Truth: <authoritative documents>
```

Human Review 必须包含：

```text
Status: Accepted Review
Task: TASK-XX
Based on: <report>
Result: <adjudication summary>
Superseded by: <updated authoritative documents>
```

归档文件保留当时的事实、判断和结论。后续变化通过 Review、ADR、Git 或新归档链接表达，不把旧报告改写成当前结论。
