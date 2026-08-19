# Semantic Closure and Recurring Blind Spots

Use this reference for refactors, architecture migrations, renames, abstraction changes, lifecycle redesigns, or any change that replaces an old mechanism with a new one.

## Semantic closure checklist

For each changed concept, verify closure across:

- definition;
- type/interface contract;
- imports/exports;
- constructors/factories;
- call sites;
- registries;
- adapters/providers;
- configuration/defaults;
- serialization/deserialization;
- hooks/events/callbacks;
- tests/fixtures/mocks;
- logs/metrics/traces;
- docs/examples;
- compatibility shims;
- legacy paths.

A migration is incomplete when old and new semantics coexist without a deliberate compatibility boundary.

## Recurring blind spots

Pay special attention to:

1. New abstraction added, old path still active.
2. Call sites migrated only partially.
3. Tests preserve legacy semantics and stay green.
4. Policy exists but is not wired into the real decision path.
5. State can be modified from multiple owners.
6. Lifecycle events are missing, duplicated, or emitted in the wrong order.
7. Error handling changes control flow but skips cleanup or observability.
8. A generic core still calls UI/CLI/provider-specific code.
9. A temporary special case leaks into the primary abstraction.
10. Configuration is snapshotted too early or has multiple sources of truth.
11. Fallbacks silently hide invalid configuration or unsupported behavior.
12. Refactor removes code but leaves tests/docs/registration/serialization.
13. Mocks validate call shape but not real integration behavior.
14. Hot paths contain blocking I/O, allocations, logging, or retries.
15. A fix removes a symptom while duplicated mechanisms remain.

## Adversarial questions

Ask:

- What old name or path would I search for if this migration were incomplete?
- Which caller can still bypass the new abstraction?
- Which test would keep passing even if the new design were never actually used?
- Where can state diverge between two owners?
- Which error path fails after a side effect but before cleanup?
- Which fallback hides a broken configuration instead of failing loudly?
