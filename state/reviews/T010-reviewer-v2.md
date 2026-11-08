# T010 focused independent re-review

Candidate: `7ac9006d6f7e5e15f48c6a98e0b9c2b8b8bb1aad` in `.worktrees/T010`.
Repair comparison: `097ef179efabe94748df878c4fb9c8a5f3b8d25c` → candidate above.
Verdict: **APPROVE** for T010's offline scope. Both prior P1 findings are resolved; no new P0/P1 identified in the focused repair.

## Resolved P1 — Denied read proposals can recover

`grade_read_trace` now retains a denied operation only when its correlated source/call ID has an observed authorization-denial/unauthorized-attempt failure and, if present, an authorization-denied tool result. The already-validated complete stream supplies start/closure/tool identity correlation. These events supply no successful read evidence; a later successful authorized relevant MCP read is still necessary. Successful unauthorized execution, uncertain/wrong-error/interrupted denial and verifier tool activity remain failures.

Regressions preserve the input trace byte-equivalent data structures, cover both frozen read tasks and denials with/without tool results, require failure when the trace contains only denial, and reject a schema-valid successful unauthorized draft followed by a valid read. Negative cases cover uncertain attribution, wrong failure/tool error, verification phase and interrupted operation. This resolves the conflation of safely denied attempts with unauthorized execution without dropping failure evidence or relaxing actual execution safety.

## Resolved P1 — Reset driver errors return bounded evidence

Every ResetBackend invocation now goes through a narrow `backend_call` boundary. Ordinary adapter/driver exceptions become sanitized ContractError without raw exception chaining and are converted by the existing evidence wrapper to failed Evidence. No retry or continued post-failure backend call is introduced. BaseException interrupts remain explicit controller responsibilities and propagate.

Regression coverage injects OSError, psycopg.OperationalError and psycopg.IntegrityError at every backend call position in both initial and sealed-cleanup paths. It checks the exact bounded failure category and operation prefix, including an exception after a simulated reset has changed state but acknowledgment is lost. Separate KeyboardInterrupt/SystemExit cases require propagation and one reset call. Documentation accurately states these semantics and leaves quarantine/persistence to T016.

## Scope and evidence

Inspected only the six-file repair diff and retained prior review context. Candidate HEAD and clean source state verified. No contracts, fixture bytes, schema, application runtime or dependency files change in this repair. The separately reviewed EventStream undotted-failure fix remains accepted as `731ab5b75414e91efea9c44d851c95b0a05c25ae`, integrated on main as `1c013d0`; its validation boundary was not broadened by this task.

Root reports 70 independent tests passing and owns the authoritative tester report/adversarial evidence; reviewer did not duplicate execution checks. Only this report was written. No DB/SQL, container/image, network, dependency install or inference action occurred.

The prior review's unchanged strengths and runtime limits continue to apply. T016 owns final lifecycle/process/budget/evidence composition and must distinguish incorrect task state from invalid or unsettled evidence. Actual DB transactions, snapshot isolation, grants, reset acknowledgment, fencing and live lifecycle semantics remain **UNRUN until their admitted runtime gates**. Approval does not authorize runtime operations or task completion; independent tester PASS remains required for integration.
