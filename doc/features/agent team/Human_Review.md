# DD-01 
- Facts: 根据 `03_runtime.md` §1.2 生成一个 `TeamAgent` 和它被注入 prompt 或领取 Task 是两个不同的步骤。第一个步骤是生成，状态从无 → IDLE，`TeamAgent` 被注册到 `MemberRegistry` 中；第二个步骤是注入 prompt 或领取 Task，状态从 IDLE → BUSY。Phase 2 阶段只实现 `TeamAgent` 从 `MasterAgent` 的需求到 `TeamAgent` 被 Registry 到 `MemberRegistry` 中的过程。
- Decision: 
  - Invariant: 
    - Spawn 的 commit point 是 member 成功发布为 IDLE；spawn 本身不意味着 TeamAgent 已开始执行工作。
  - Mechanism: 
    - 只创建并发布被动 TeamAgent execution wrapper，不启动后台线程、不立即调用模型。
    - Phase 2 定义并 fake-test TeamAgent.run(prompt) execution boundary。
- Why: 
  - Phase 2 只实现 spawn vertical slice，不提前实现 Phase 3～5 的 messaging、task collaboration、shutdown 或 teardown 行为。
- Deferred: 
  - 谁触发 run： Phase 3 messaging / Phase 4 task collaboration。
  - 是否需要后台线程：Deferred。
  - fatal supervision / shutdown：Phase 5。
- Verification:
  - ARCH-04 通过 fake-loop contract test 验证。 


# DD-02
- Facts: `MasterAgent` 的 AgentRuntime 是启动该 Agent 时就已经创建，session_id 也是 AgentRuntime 的参数之一。
- Decision: 
  - Invariant:
    - 一个 Master session 对应一个 TeamRuntime composition context。
    - Master AgentRuntime 与 TeamRuntime 是 sibling，不相互拥有状态。
    - TeamAgent 与 Master 共享 session_id。
    - 不要让 create_master_runtime() 知道 TeamRuntime，但允许它增加通用的 per-instance injection seam。
  - Mechanism: 
    - master_agent() composition scope 显式持有 TeamRuntime。
    - Master 的 spawn handler closure/bound handler 引用 TeamRuntime。
    - 不在 AgentRuntime 增加 team 字段。
    - TeamRuntime 在 Master session composition 时建立为空 team；第一次 spawn_teammate 只创建 member，不负责首次创建 TeamRuntime。
    - Master session composition scope 负责生成 session_id，并显式传给 Master AgentRuntime 与 TeamRuntime；RuntimeFactory 不再是该 session_id 的唯一生成者。
- Why:
  - AgentRuntime 和 TeamRuntime 的并非同一概念/层次，避免混淆。
- Deferred: None


# DD-03
- Facts: `MasterAgent` 的在创建时就拥有了自己的 `session_id`、workspace、model/fallback model 和 EventSink。 
  - Invariant:
    - TeamAgent 有独立 AgentRuntime/state/history/agent_id/runtime paths。
    - TeamAgent 与 Master 属于同一 session，当前无 worktree，因此共享 workspace。
    - TeamAgent 不直接与用户交互。
  - Mechanism(Phase 2): 
    - model/fallback 默认继承 parent runtime policy。
    - NonInteractiveInteraction。
    - EventSink 暂用 NullEventSink，避免 Phase 2 意外引入 child-output routing。
    - TeamRuntime 使用 .agents/runs/<session_id>/tasks 作为 session-scoped TaskStore 路径。
- Provisional execution policy:
  - READ_ONLY memory；
  - read_file/glob/load_skill；
  - max_turns=30。
  - MemoryMode.READ_ONLY namespace = "master"(Provisional Phase-2 mechanism)
- Why:
  - `session_id` 每个会话一个，故 TeamAgent 与 MasterAgent 共享 `session_id`。
  - 若无 worktree 设计时，每个 `session_id` 下所有 Agent 共享 workspace。
  - TeamAgent 与 MasterAgent 的关系和 Subagent 与 MasterAgent 的关系相似，故 TeamAgent 的 EventSink 执行方式参照 Subagent 的 EventSink 执行方式。
- Deferred: 正式 TeamAgent memory namespace / tool capability / event routing / max-turn policy 在真正进入执行能力时重新裁决；Phase 2 的值不提升为 Architecture invariant。


# DD-04
- Facts: RuntimeFactory 创建 AgentRuntime 时已经创建 runtime directories；但当前 AgentRuntime 没有 destroy()/close() contract。
- Decision: 
  - Invariant:
    - 当前 Phase 的 rollback 保证逻辑资源/ownership rollback，不承诺删除 RuntimeFactory 已创建的 filesystem diagnostic artifacts。并把这个 accepted delta 传播回 05_failures.md。
    - STARTING → IDLE 是 spawn transaction 的 commit point。
    - 只有 Lifecycle 创建 AgentRuntime
    ``` text
    Tool
    → Coordinator
    → Lifecycle
    → RuntimeFactory
    ```
  - Mechanism: 
    - Coordinator → orchestrate
    - Lifecycle → owns creation transaction
    - TeamAgent → execution wrapper
- Phase-2 implementation contract:
    - TeamCoordinator.spawn_teammate(*, parent_runtime, agent_name) ->  MemberRecord
    - LifecycleManager.spawn(*, parent_runtime, agent_name) -> MemberRecord
    - TeamAgent.run(prompt) -> existing query_loop result
    - SpawnError(TeamError) 作为 spawn domain failure
    - 参数名称和具体返回包装可在不改变职责边界的前提下做局部实现调整；若需要改变调用方向/ownership，则重新报告 Design Delta。

``` text
Runtime created
    ↓
TeamAgent wrapper created
    ↓
Registry STARTING
    ↓
Lifecycle owns wrapper/runtime
    ↓
SPAWN_SUCCESS
    ↓
IDLE = COMMIT
```
在 commit 前任何一步失败：
``` text
reverse cleanup
+ STARTING record → SPAWN_ROLLBACK
+ Lifecycle 不保留 runtime/wrapper reference
```

- Why: 
  - MemberRegistry owns: agent_id / agent_name / MemberState
  - LifecycleManager owns: AgentRuntime / TeamAgent wrapper 的可达执行资源
- Deferred: None