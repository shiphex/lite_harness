# TASK-08 Design Review

Status: Accepted Review

Task: TASK-08 Optional Real-model E2E Smoke

Based on: [TASK-08_preflight.md](TASK-08_preflight.md)

Result: 用户接受 DD-01～DD-03；设计已传播至 `07_test_plan.md` 与 `08_tasks.md`。`SMOKE-01` 保持 `[ ]`，真实模型 smoke 尚未实现或运行。

Reviewer: User（2026-10-01 明确回复“同意DD-01～DD-03”）

Superseded by: [07 测试计划](../07_test_plan.md) §1.3 / §4.5 与 [08 当前任务](../08_tasks.md) TASK-08

Prepared by: Codex

Baseline: `4b575b6c437bdbbf3c82467ebf73b5099724caec` (`feature/team`)，预检开始时工作区干净

## 审阅依据

- TASK-07 / Phase 6 已接受，见[完成审阅](TASK-07_completion-review.md)；全量 pytest 在当前基线为 **364 passed in 4.06s**。Phase 6 两条全链路测试使用 fake loop，真实模型 smoke 在现行 [07 测试计划](../07_test_plan.md)中仍为可选项。
- 当前 TeamAgent 默认进入统一 query_loop，经 adapter factory 调用模型；Master bound 工具能创建成员、任务并同步分配。具体入口、状态所有权和失败路径见[预检报告](TASK-08_preflight.md)。
- 用户启动的本地 llama.cpp 服务返回 `GET /health` 200、`GET /v1/models` 200；模型 ID 为 `unsloth/Qwen3.5-4B-GGUF:UD-Q6_K_XL`。建议经项目现有 OpenAI adapter 使用 `http://127.0.0.1:8000/v1` 与本地无鉴权占位值 `no-key`；尚未验证推理或 tool calling。

## 设计差异与裁决

### DD-01：smoke 的执行入口与覆盖范围

**建议接受。** 增加一个默认不由 pytest/CI 执行的显式 smoke 入口。在临时 workspace 中组装真实 TeamRuntime、RuntimeFactory、Master bound handler 与 TaskStore，通过 Master 工具创建一名 TeamAgent 和一项简短任务，再让 TeamAgent 的默认 query_loop 调用本地真实模型并完成任务。Master 工具由脚本驱动，Master 本身不调用模型；报告明确这条覆盖边界。

**裁决：接受。**

**备选：**人工运行完整 CLI，让模型驱动 Master 的工具选择。此法覆盖交互入口，但结果更受提示词影响，也更难隔离运行 artifacts 与重现失败。把 live smoke 直接纳入默认 pytest 则会使常规回归隐式发起外部请求。

### DD-02：本地服务配置与调用边界

**建议接受。** 本次本地服务使用 `api=openai`、`model_url=http://127.0.0.1:8000/v1`、`model_name=unsloth/Qwen3.5-4B-GGUF:UD-Q6_K_XL`、本地无鉴权占位值 `no-key`。入口支持显式覆盖 API 类型、URL 和模型名；如换成需鉴权服务，真实密钥只从环境变量读取。使用临时 workspace、一项任务、最多 3 个 TeamAgent turn 和每次最多 512 个输出 token；不输出密钥或原始敏感响应。现有 API 429/529 重试行为不因 smoke 改写，报告须如实记录触发的失败。

**裁决：接受。**

### DD-03：通过标准与失败处理

**建议接受。** 必须观察到真实模型响应触发当前任务的 `complete_team_task`、TaskStore 中的 owner 与 `completed` 状态正确、成员回到 IDLE，且 teardown 最终释放，才判定通过。服务连接/协议问题、模型未调用完成工具、任务执行异常、teardown 拒绝分别保留实际结果，不以“端口可达”或跳过替代通过。设计接受后在 `07_test_plan.md` 增加可选 `SMOKE-01` 检查项，完成审阅接受前保持 `[ ]`；不改动已完成的 SC-01～07 与 Phase 6。

**裁决：接受。**

## 审阅结论

DD-01～DD-03 已获用户接受，`SMOKE-01` 已列入可选测试计划并保持未完成。用户要求先提交本轮设计文档，后续实现与真实模型运行将在新对话继续；完成后仍须独立完成审阅。
