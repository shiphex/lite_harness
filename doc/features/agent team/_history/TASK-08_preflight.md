# TASK-08 Preflight Brief

Status: Archived / Non-authoritative

Task: TASK-08 Optional Real-model E2E Smoke

Baseline: `4b575b6c437bdbbf3c82467ebf73b5099724caec` (`feature/team`)，预检开始时暂存区与工作区均无改动

Outcome: Ready for design review；DD-01～DD-03 待人工裁决，本地服务已探测但尚未发送推理请求

Source of Truth: [`../01_problem.md`](../01_problem.md)～[`../08_tasks.md`](../08_tasks.md)；本报告只记录基线、现状、建议和待审差异

## Preflight Verdict

**Ready for design review; blocked for implementation and live execution.** TASK-07 / Phase 6 已完成验收，但覆盖该阶段的全链路测试使用 fake loop。`../08_tasks.md` 把真实模型 E2E smoke 列为 Phase 6 后的可选项目，不阻塞 MVP。用户本轮要求继续执行该任务，故沿用 TASK-08 编号启动预检；尚无已接受的 smoke 范围和验收标准，不能把既有 364 项回归、端口可达或模型列表响应当作真实模型 smoke 通过。

## 基线与当前证据

- `git status --short --branch` 显示 `feature/team...origin/feature/team [ahead 4]`，预检开始时无暂存或未暂存改动；HEAD 为上述提交。完成的 Phase 6 审阅见 [TASK-07_completion-review.md](TASK-07_completion-review.md)。
- `.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider` → **364 passed in 4.06s**。此前测试均未发起真实模型调用；[`../07_test_plan.md`](../07_test_plan.md) §1 的真实模型 smoke 仍是 optional。
- 用户已启动 llama.cpp 本地服务。预检中的 Python TCP socket 连接 `127.0.0.1:8000` 和 `::1:8000` 均成功；只读 `GET /health` 与 `GET /v1/models` 均返回 HTTP 200，后者给出的模型 ID 为 `unsloth/Qwen3.5-4B-GGUF:UD-Q6_K_XL`。这些检查未发送推理请求，也未证明工具调用成功。
- README 和 `config/config.py:62`～`:67` 默认 `anthropic`、`http://localhost:8000`、`claude-fable-5`、`no-key`；当前 llama.cpp 服务的 `/v1/models` 与 OpenAI-compatible 路径匹配，拟配置 `api=openai`、`model_url=http://127.0.0.1:8000/v1`、上述模型 ID 与本地无鉴权占位值 `no-key`。预检未使用或写入真实令牌。
- `core/agent.py:124`～`:137` 在 Master session 创建 TeamRuntime 并绑定 Master 专属工具。`team/lifecycle.py:325`～`:326` 为 TeamAgent 复制 parent 的模型配置；`team/agent.py:30`～`:32`、`:45`～`:58` 的默认 `run()` 进入既有 `query_loop`。
- `core/loop.py:455`～`:463` 经 `api/adapter_factory.py:12` 的适配器发出 ModelRequest。`team/coordinator.py:84`～`:109`、`:197`～`:213` 同步分配并执行一轮；`team/task_tools.py:109`～`:133` 只允许当前 owner 在活动任务轮调用 `complete_team_task`。
- `tests/team/test_phase6_integration.py:1`～`:23` 用确定性 fake loop 验证组合链；仓库中没有独立的显式真实模型 smoke 入口。`core/runtime.py:76`～`:96` 可把 runtime artifacts 放在传入 workspace 下，适合隔离一次性检查。

## 需求映射和缺口

| 来源 | 已有证据 | TASK-08 待补 |
| --- | --- | --- |
| `01_problem.md` SC-01/02/04/06 | Phase 0～6 已接受的创建、统一 loop、生命周期和自动回归 | 一次真实模型响应是否能经 TeamAgent 工具完成团队任务 |
| `07_test_plan.md` §1 optional real-model smoke | 明确列为 Phase 6 后可选，未定义独立检查项 | 可重复的显式运行入口、通过标准及服务错误分类 |
| `08_tasks.md` Optional Real-model E2E Smoke | MVP 已结束，TASK-08 现启动预检 | 当前任务简报、设计裁决、运行证据与独立完成审阅 |

## 方案和设计差异待审阅

### DD-01：真实模型验证入口

**建议接受：**增加一个默认不由 pytest/CI 执行的显式 smoke 入口。入口在临时 workspace 中使用实际 TeamRuntime、RuntimeFactory、Master bound handler 与 TaskStore，经 Master 工具创建一个 TeamAgent 和一项简短任务，再让其默认 `query_loop` 调用本地真实模型并调用 `complete_team_task`。Master 工具调用由 smoke 入口驱动，Master 本身不调用模型；这条边界写入结果，避免声称验证了模型驱动的 Master 决策。

**备选：**人工操作完整 CLI，让模型驱动 Master 的 spawn / assign；覆盖更广，但结果受提示词和交互影响，较难形成稳定检查，且运行 artifacts 位于仓库 workspace。将实时 pytest 作为默认测试则可能在常规回归中意外发起网络请求。

### DD-02：服务配置、隔离与资源上限

**建议接受：**smoke 仅显式运行；调用方提供或确认 API 兼容类型、URL、模型名及鉴权方式。真实密钥只按环境变量名读取；本地无鉴权服务允许使用 README 的 `no-key` 占位值。运行前验证配置，在临时 workspace 中创建 artifacts，只执行一项任务，限制 TeamAgent turn 数和每次最大输出 token；不输出密钥或原始敏感响应。服务连接、协议或凭据失败应明确报告，不标记为通过。

**已探测配置：**本地 `/health` 与 `/v1/models` 可用，拟以 `api=openai`、`model_url=http://127.0.0.1:8000/v1`、`model_name=unsloth/Qwen3.5-4B-GGUF:UD-Q6_K_XL` 和无鉴权占位值 `no-key` 运行。服务是否能正确处理当前项目的 tool schema 与模型响应，仍须在设计接受后通过实际 smoke 验证。

### DD-03：通过标准与失败语义

**建议接受：**只有观察到至少一次真实模型响应、当前 TeamAgent 通过团队工具完成分配任务、TaskStore 保留实际 owner 与 `completed` 状态、Registry 回到 IDLE 且 teardown 完成最终释放，才记为通过。若模型未调用完成工具、模型服务异常、任务执行异常或 teardown 拒绝，记录具体失败与仍可观察的任务/成员事实；不静默重试成“通过”。设计接受后在 `07_test_plan.md` 新增可选 `SMOKE-01` 检查项，完成审阅接受前保持 `[ ]`，不重写既有 SC-01～07 与 Phase 6。

## 验证计划与下一门槛

- 本次预检只更新 `../08_tasks.md`、本报告及 `../Human_Review.md`；不修改 01～07、产品代码或现有测试，也不发送真实模型请求。检查三份文档的相对链接与 `git diff --check`。
- 设计接受后，验证入口的参数校验、显式运行边界和密钥不回显；执行全量 pytest，确认常规回归仍不发起网络请求。使用已探测的本地服务配置只运行本次已接受范围的一次真实模型 smoke，记录无密钥的命令形式、结果与边界。
- 若服务不兼容或模型未按提示调用工具，保留真实失败证据和当前任务，不将 Optional Smoke 勾选；需要改变任务语义或产品行为时先补设计审阅。完成后仍需独立人工完成验收。
- 下一道门槛为 [`../Human_Review.md`](../Human_Review.md) 对 DD-01～DD-03 的逐项裁决。Ready 仅表示可送审，不表示获准实现或运行真实模型。
