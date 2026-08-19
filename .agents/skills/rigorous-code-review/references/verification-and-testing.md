# Verification and Testing

Use this reference when review quality depends on runtime evidence, tests, benchmarks, static analysis, simulation, or integration behavior.

## Verification hierarchy

Choose the strongest relevant evidence:

- build/compile;
- unit tests;
- integration tests;
- end-to-end tests;
- type/static analysis;
- sanitizer/race detector;
- security scan;
- benchmark/profiling;
- simulation;
- hardware-in-the-loop;
- staging/canary;
- replay/backtest.

Do not run irrelevant checks merely to increase the count of successful commands.

## Test quality questions

Ask:

- Would the test fail before the fix?
- Is it asserting public behavior or an implementation detail?
- Does it cover the actual failure path?
- Does it include boundary conditions?
- Does it include timeout/cancellation/retry/recovery when relevant?
- Can mocks hide the defect?
- Is the test deterministic?
- Is there a regression test for a bug fix?
- Do old tests now assert obsolete semantics?

## Evidence discipline

Never claim:

- a command passed if it was not run;
- a benchmark improved without measured data;
- a race is impossible without examining synchronization;
- integration behavior is safe if only mocks were tested.

If a concern is plausible but unverified, label it **Needs verification** instead of presenting it as a confirmed defect.

## Risk-based verification

Low-risk refactor:
- targeted unit tests;
- static checks;
- semantic closure search.

Medium-risk behavior change:
- targeted tests plus integration path;
- error-path verification;
- compatibility checks.

High-risk change:
- independent verification path;
- failure injection where possible;
- performance/safety evidence;
- simulation/HIL/staging/replay as appropriate.
