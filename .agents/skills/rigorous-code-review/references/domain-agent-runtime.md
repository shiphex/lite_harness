# Domain Overlay: Agent / Harness / LLM Runtime

Apply when reviewing agent runtimes, tool loops, subagents, memory/context systems, hooks/events, model adapters, permission systems, or CLI/UI separation.

Check:

- shared loop versus duplicated agent loops;
- agent-specific state, memory, policy, prompts, and filesystem isolation;
- Runtime/service ownership;
- model-provider adapter contracts;
- tool schema/result normalization;
- hook as interception/policy versus event as fact versus log as diagnostic record;
- permission/approval policy on the real execution path;
- context compaction and memory lifecycle;
- subagent cancellation and parent/child lifetime;
- tool timeout, partial result, retry, and side-effect idempotency;
- event ordering, correlation, and replay assumptions;
- CLI/UI independence from core logic;
- output/event/log duplication;
- hidden direct calls that bypass runtime abstractions;
- prompt/config snapshots that become stale;
- provider-specific assumptions leaking into common contracts.

Important invariants often include:

- one authoritative owner for agent execution state;
- subagents reuse shared orchestration without accidentally sharing mutable memory;
- hooks may influence execution; events should describe what happened;
- logs should not become a second domain-event transport;
- cancellation and tool failures must not orphan child work.
