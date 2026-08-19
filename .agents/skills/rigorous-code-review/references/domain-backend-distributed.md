# Domain Overlay: Backend / Distributed / Infrastructure

Apply to APIs, services, storage, migrations, queues, caches, schedulers, deployment, and infrastructure code.

Check:

- API/schema compatibility;
- migrations and rollback;
- retry semantics and idempotency;
- duplicate delivery;
- timeout and circuit-breaking behavior;
- partial failure;
- cache invalidation and versioning;
- consistency assumptions;
- rate limits and resource exhaustion;
- authentication and authorization;
- deployment ordering;
- feature flags;
- observability;
- rollback and recovery.

Explicitly inspect failure between distributed side effects. A sequence that is correct when all services succeed may be incorrect under partial success.
