# Severity and Merge Policy

Use this reference when assigning severity, discussing merge readiness, or resolving disagreement about priority.

## P0 — Critical / must not merge

Examples:

- exploitable security boundary failure;
- credible unsafe hardware behavior;
- data loss or unrecoverable corruption;
- incorrect financial execution or missing hard risk limit;
- deterministic crash or broken primary behavior;
- severe concurrency fault in a critical path;
- build/release failure preventing the intended artifact from functioning.

## P1 — High / normally blocks merge

Examples:

- reproducible correctness bug;
- broken contract with meaningful blast radius;
- race, deadlock, leak, cancellation, or lifecycle defect;
- backwards-incompatible change without migration strategy;
- partial failure leaving inconsistent state;
- architecture boundary violation likely to cause near-term regression;
- missing verification for newly introduced high-risk behavior.

## P2 — Medium / should fix or explicitly accept

Examples:

- bounded edge-case bug;
- material maintainability or observability gap;
- credible performance/resource regression with limited blast radius;
- incomplete tests for non-critical behavior;
- abstraction drift or duplicated mechanism that increases future risk.

A P2 may block in safety-critical, real-time, security-sensitive, or financial execution code.

## P3 — Low / optional

Examples:

- readability polish;
- naming improvement;
- minor simplification;
- documentation improvement;
- non-required refactor;
- style preference not enforced by project rules.

Do not inflate severity to make feedback more persuasive.

## Merge decision

End with exactly one:

- **BLOCK** — unresolved P0 exists.
- **CHANGES REQUESTED** — unresolved P1 exists, or risk-specific P2 must be fixed before merge.
- **APPROVE WITH FOLLOW-UPS** — no P0/P1; remaining items are explicitly non-blocking.
- **APPROVE** — no material defect found within reviewed scope and verification is sufficient for the risk level.
