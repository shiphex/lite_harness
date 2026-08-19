---
name: rigorous-code-review
description: Use for strict reviews of commits, PRs, diffs, refactors, bug fixes, architecture changes, and merge-readiness checks across general software, agent runtimes, embedded/robotics, ML/data, quantitative/trading, and backend/distributed systems.
version: 2.0.0
---

# Rigorous Code Review

Review code to reduce engineering risk, not to police style.

The core questions are:

1. Does the change satisfy its intended behavior?
2. Does it preserve contracts and invariants across normal and failure paths?
3. Does it preserve or improve system design and code health?
4. Is there enough evidence to merge safely?
5. What remains uncertain?

Prefer evidence, reproducible failure paths, and system-level reasoning over personal taste.

## 1. Establish the review contract

Before judging the code, identify as much as possible:

- exact repository / branch / PR / commit;
- comparison base;
- intended behavior or refactor goal;
- important constraints;
- risk level;
- available verification methods.

If an exact commit SHA is given, review that commit rather than a moving branch head.

If important context is unavailable, continue with the inspectable scope and state the limitation. Never invent unseen code, line numbers, tests, or runtime behavior.

Do not modify code unless the user explicitly asks for fixes.

## 2. Review in this priority order

1. safety, security, data or financial integrity;
2. correctness and behavioral contracts;
3. architecture, ownership, dependency direction, and lifecycle;
4. failure recovery, concurrency, compatibility, and resource bounds;
5. performance and scalability;
6. tests and verification quality;
7. observability and operability;
8. maintainability and clarity;
9. style and minor polish.

Do not let style comments obscure system-level defects.

## 3. Review the system change, not only the diff

Read changed lines, but also inspect enough surrounding code to understand:

- callers and callees;
- interfaces and implementations;
- constructors, factories, registries, and adapters;
- state ownership and mutation;
- configuration and defaults;
- tests, fixtures, mocks, examples, and docs;
- cleanup, shutdown, retry, rollback, and recovery.

A locally correct diff can still be a system-level regression.

## 4. Build a change map

For each changed concept, trace:

**input → validation → policy → state transition → side effect → output/event → cleanup**

Identify:

- stable contracts;
- state owners;
- side effects;
- lifecycle transitions;
- external boundaries;
- critical invariants.

Do not start with line-by-line style review before understanding the main execution path.

## 5. Check semantic closure

Whenever a concept is renamed, moved, generalized, replaced, or given new semantics, search the repository for both the old and new forms.

Verify that the change is closed across:

- definitions and type contracts;
- imports and exports;
- constructors and factories;
- call sites;
- adapters/providers;
- configuration and serialization;
- hooks/events/callbacks/registrations;
- tests/fixtures/mocks;
- logs/metrics/traces;
- docs/examples;
- compatibility or legacy paths.

Ask:

> Did the conceptual change propagate through the whole system, or are two competing semantics now alive?

For the detailed closure checklist and recurring migration blind spots, read:
[references/semantic-closure-and-blindspots.md](references/semantic-closure-and-blindspots.md)

## 6. Trace behavior and lifecycle

For critical paths, inspect:

- valid and invalid inputs;
- boundaries and empty values;
- partial success;
- timeout;
- cancellation;
- retry;
- dependency failure;
- repeated invocation;
- shutdown during work;
- restart/recovery.

Model lifecycle where relevant:

**create → initialize → active → transition → stop/cancel → cleanup → terminal/recover**

Check preconditions, postconditions, state ownership, idempotency, cleanup, rollback, and event/callback ordering.

## 7. Check risk-specific concerns

Apply only when relevant:

- concurrency and async;
- resource lifetime and leaks;
- performance or real-time constraints;
- security/trust boundaries;
- destructive side effects;
- compatibility/migrations;
- persistence and recovery.

Do not force every checklist onto every project.

## 8. Review tests as evidence, not as an oracle

Tests reveal intended behavior, but may preserve the wrong contract.

Ask:

- Would this test fail before the fix?
- Does it test behavior rather than implementation detail?
- Does it cover the actual failure mode?
- Are failure/cancellation/recovery paths covered?
- Do mocks erase the integration risk?
- Are old tests asserting obsolete behavior?

Never claim a command passed unless it was actually run successfully.

For deeper verification guidance, read:
[references/verification-and-testing.md](references/verification-and-testing.md)

## 9. Apply domain overlays only when triggered

Read only the relevant file:

- Agent / harness / LLM runtime:
  [references/domain-agent-runtime.md](references/domain-agent-runtime.md)
- Embedded / real-time / robotics:
  [references/domain-embedded-robotics.md](references/domain-embedded-robotics.md)
- ML / VLA / data pipelines:
  [references/domain-ml-data.md](references/domain-ml-data.md)
- Quantitative / trading systems:
  [references/domain-quant-trading.md](references/domain-quant-trading.md)
- Backend / distributed / infrastructure:
  [references/domain-backend-distributed.md](references/domain-backend-distributed.md)

If none applies, do not load a domain reference.

## 10. Classify findings and make a merge decision

Use P0–P3 severity and end with one merge decision.

Read the policy only when preparing findings or when severity is disputed:
[references/severity-and-merge.md](references/severity-and-merge.md)

For P0–P2 findings, use an evidence-based structure. See:
[references/finding-format.md](references/finding-format.md)

## 11. Final adversarial sweep

Before finalizing, search for:

- old API names;
- obsolete branches;
- duplicate implementations;
- dead code;
- stale tests or docs;
- unused flags;
- hidden fallbacks;
- inconsistent defaults;
- bypass paths around the new abstraction.

This sweep is mandatory for refactors and architecture migrations.

## 12. Final output

Use this order:

1. **Scope and verdict**
2. **Verification performed**
3. **Findings**, ordered P0 → P1 → P2 → P3
4. **Positive observations**, only when meaningful
5. **Residual risks / missing evidence**
6. **Merge recommendation**

Do not say “LGTM” without stating scope and evidence.

## Fast checklist

Before finalizing, confirm:

- [ ] Revision, scope, intent, and critical invariants are explicit.
- [ ] Design and real call paths were reviewed before style.
- [ ] Semantic closure was checked.
- [ ] Failure, cancellation, cleanup, ownership, and lifecycle were considered.
- [ ] Risk-specific concerns were checked where relevant.
- [ ] Tests were treated as evidence that may itself be wrong.
- [ ] Verification claims match evidence actually observed.
- [ ] Relevant domain overlay was applied only if needed.
- [ ] Findings are concrete, severity-ranked, and actionable.
- [ ] Residual uncertainty and merge decision are explicit.
