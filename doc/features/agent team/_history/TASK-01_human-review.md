# TASK-01 Human Review

Status: Accepted Review
Task: TASK-01
Based on: [`TASK-01_gap-analysis.md`](TASK-01_gap-analysis.md)
Result: DD-01～04 adjudicated
Superseded by: updated `../02_architecture.md`、`../03_runtime.md`、`../04_contracts.md`、`../05_failures.md`、`../06_decisions.md`、`../07_test_plan.md`、`../08_tasks.md`

---

## DD-01
- Fact: 目前已经确定了 team 文件夹的结构，Coordinator、Registry、MessageBus、TaskStore、LifecycleManager 也直接或间接由 TeamRuntime 持有。
- Decision:
  - Invariant:
    - TeamRuntime 是 team composition root。
    - TeamRuntime 持有/组装 team-scoped shared services。
    - TeamRuntime 不并入 AgentRuntime。
  - Mechanism:
    - 具体代码落点不作为架构约束。
    - Phase 1 根据现有 package convention 选择最小且职责清晰的落点。
    - 若没有合适的已有模块，允许新增 team/runtime.py 文件。
- Why:
  - TeamRuntime 状态不属于 AgentRuntime 状态，TeamRuntime 属于 Team， AgentRuntime 属于 Agent。
  - 文件位置不是当前 architecture invariant；Phase 1 应优先遵循现有 package convention 和单一职责，在“不制造无意义模块”和“不混淆 composition responsibility”之间取最小方案。
- Deferred:
  - TeamRuntime 放在哪里暂时不确定，后续再考虑(until Phase 1 / TASK-02 planning)。


## DD-02
- Fact: 授权模块向 MemberRegistry 请求/报告状态转换，MemberRegistry 是唯一 authoritative owner。但当前设计缺少由授权模块向 MemberRegistry 提交并校验 MemberState transition 的闭环机制。
- Decision:
  - invariant:
      - 在相关设计文档中增加相关接口设计，所有 MemberState 变更必须经过 MemberRegistry 的受控状态转换接口
      - STOPPED / FAILED member record 在 TeamRuntime 生命周期结束前仍然可查询
      - unregister 仅用于：spawn 发布成功前的 rollback；TeamRuntime 最终释放。
- Why:
  - 目前的设计文档中确实没有相关接口设计。
  - 但还不确定具体需要哪些接口。
- Deferred: 使用什么接口、哪些接口、接口名称等 Phase 1 中再考虑。
- Verification:
  - 正常 shutdown 流程：
    ```
    TeamAgent shutdown
    ↓
    Registry.get(agent_id)
    ↓
    仍返回该 member
    state == STOPPED
    ```
  - Fatal：
    ```
    runtime failure
    ↓
    Registry
    ↓
    state == FAILED
    ```
  - 非法 transition：
    ```
    STOPPED → BUSY
    ↓
    reject
    ```


## DD-03
- Fact: 现有 task_system 已具备目标任务操作能力，但相关能力分散在 TaskStore instance 与绑定全局 TASKS 的 module functions 中，与 TeamRuntime-owned、可注入 TaskStore 的设计不一致。当前报告给出三个方案：
  1. 让现有 task-system 操作接受显式 store，保留缺省全局 TASKS 兼容当前工具；
  2. 在 team/tasks.py 重写任务行为；
  3. 让所有 TeamRuntime 共用全局 TASKS。
- Decision:
  - invariant:
    - 每个 TeamRuntime 使用 team-scoped TaskStore；
    - 不复制第二套 task state / task behavior；
    - 保持当前全局工具路径向后兼容。
  - mechanism:
    - 为现有 task-system operation 增加显式 store 注入。(Preferred implementation direction)
- Why:
  - 方案比较：
    | 方案           | 复用 | Team 隔离 | 兼容旧代码 | 新复杂度 |
    | ---------------- | --- | ------- | ----- | ---- |
    | 显式 store 注入      | 高   | 高     | 高     | 中    |
    | 重写 TeamTaskStore | 低   | 高       | 高     | 高    |
    | 共用 global TASKS  | 高   | 低       | 高     | 低    |
  - 选择方案：显式 store 注入。该方案不改变原有 task-system 体系，只让现有 task-system 操作接受显式 store，代码增改量最小，也能保证 Team 对任务的隔离。
- Deferred: 最终采用函数参数、bound handler 还是薄 adapter，结合 Phase 1/4 的现有代码选择。
- Verification: 
    - Reuse:
        没有复制第二套 task logic
    - Isolation:
        两个 TeamRuntime 的 store 不互相污染
    - Compatibility:
        原有使用 global TASKS 的测试仍然通过
    - Complexity:
        没有为了 store injection 引入新的 scheduler/task subsystem

## DD-04
- Fact: 设计测试中引用 AgentRuntimeFactory，现有代码实际符号为 RuntimeFactory（evidence: `f90561f/core/runtime.py:143`）。
- Decision: 使用 RuntimeFactory
- Why: 现有代码实际使用 RuntimeFactory。
- Deferred: None





