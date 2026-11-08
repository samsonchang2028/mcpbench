# T040 prospective recovery controller tester

Offline implementation verdict: **PASS**. Live retry: **NOT AUTHORIZED / UNRUN**. Frozen controller SHA-256 `c9809246f788daa3f118c17de44f1a59e28ba2861af3a2f30de41e7ed29ba3b9`. No inference, main invocation, actual resource sampling, child controller, native service or candidate mutation. Only this report written. Original failed attempt remains unchanged.

Read T040-recovery context and retained preflight/result context. Commands: bounded `diff -u` of immutable01 and prospective02 (exit 1 correctly indicates the intended delta), then `python3` in-memory compile, exact normalized-AST comparison and mocked helper tests. All sample inputs, inventory/API calls, clock and load averages were synthetic; `sample_bounded` subprocess invocation was mocked.

| Check | Actual result | Evidence |
| --- | --- | --- |
| Frozen identity and syntax | PASS | c9809246f788daa3f118c17de44f1a59e28ba2861af3a2f30de41e7ed29ba3b9 |
| Only telemetry delta | PASS | Removing two new dictionary entries yields exact old AST; request, monitors, bounds, aborts, cancellation, validation and dispatch unchanged |
| Aggregate CPU parsing | PASS | Aggregate cpu row only, all ten counters retained, including guest fields for later correct arithmetic |
| Load tuple and JSON fields | PASS | Three load averages survive JSON serialization as numbers |
| Existing sample fields retained | PASS | Mocked proc/inventory/API values retained unchanged |
| Aggregate deadline retained | PASS | Mocked sample child; 1.5sec total timeout and CPU payload preserved |

No new P0/P1 found. Exact AST equivalence after removing the two added telemetry fields proves unchanged 120-second request deadline, 4096/512 budgets, 2-second scheduled monitor, three-sample RAM/swap thresholds, health/OOM comparisons, one-request policy and cancellation handling. Raw aggregate CPU counters support later delta calculation; compute CPU busy using the first eight counter fields to avoid counting guest time twice. Load averages are supplementary observations, not instantaneous CPU utilization. Existing first-attempt missing-CPU evidence remains missing; this prospective change cannot repair that historical result.

This PASS establishes offline readiness only. No second request was executed or approved. Any future retry still requires the user's decision, complete fresh 60-second admission and immediate health/model/residency refresh under unchanged gates and stop thresholds. Root's separate read-only recovery observations were not sampled or assessed by this tester task.
