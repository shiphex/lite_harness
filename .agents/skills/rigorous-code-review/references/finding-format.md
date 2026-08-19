# Finding Format

Use this reference when writing P0–P2 findings.

Each finding should let another engineer independently verify the problem.

```markdown
### [P1][correctness] Short actionable title
**Location:** `path/to/file.py:L120-L136`
**Confidence:** high | medium
**Invariant/contract:** What must remain true.
**Failure path:** Concrete trigger.
**Impact:** Consequence and blast radius.
**Evidence:** Verified code path or execution evidence.
**Recommended direction:** Smallest reasonable fix.
**Verification:** Evidence that would prove the fix.
```

Rules:

- one root cause per finding;
- exact locations only when verified;
- explain why, not merely what;
- do not report hypothetical issues as facts;
- do not duplicate linter output unless it has semantic impact;
- do not bury P0/P1 under P3 comments;
- distinguish required changes from optional improvements.

If multiple symptoms share one architectural root cause, report the root cause first and group symptoms beneath it.
