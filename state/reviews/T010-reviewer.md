# T010 independent reviewer

Candidate: `097ef179efabe94748df878c4fb9c8a5f3b8d25c` in `.worktrees/T010`, compared with `272ce58`.
Verdict: **CHANGES REQUIRED**. Two open P1 findings; no P0 finding identified.

## P1 — Safely denied proposals invalidate otherwise passing read evidence

Location: `eval/grading/oracle.py:180–183` (`grade_read_trace`).

Trigger: a complete execution trace contains a registered but unauthorized draft-tool proposal that is safely rejected (`tool.started` followed by `tool.failed`/authorization denial, with zero execution/writes), followed by a successful authorized MCP read containing the required record IDs. The permission checks run on every `tool.*` event and reject the denied proposal before considering the successful read.

Impact: this confuses a recovered model/tool error with actual unauthorized execution. A valid unchanged-state read task with the right answer and successful read evidence receives failed trace evidence solely because the safely denied attempt remains in its trace. This conflicts with `contracts/PROTOCOL.md` terminal truth table and explicit rule that a denied `unauthorized_attempt` with zero executions may recover, and with `docs/EVALUATION_PLAN.md` retaining recovered errors without automatically invalidating a later correct task. It can bias measured task outcomes or comparison eligibility against strategies that recover after a denial.

Smallest useful fix: preserve/attribute denied attempts separately from successful unauthorized execution. A safely denied operation must neither supply successful read evidence nor invalidate later valid read evidence. Continue to reject actual unauthorized successful execution and forbidden verifier activity. Add a complete-stream regression case with denied draft attempt plus successful read, alongside a successful unauthorized-execution rejection. Do not drop the denied events to obtain a pass.

## P1 — Real PostgreSQL driver failures escape the promised reset evidence interface

Locations: `eval/grading/oracle.py:32–40` (`evidence`) and `eval/reset/contract.py:40–57` (backend calls).

Trigger: `ResetBackend.read_mapping`, `reset_seed` or `snapshot` raises the pinned driver's `psycopg.OperationalError`/other `psycopg.Error`. The decorator only catches its listed built-in/contract exception families. Inspected pinned psycopg source declares `OperationalError(DatabaseError)`, `DatabaseError(Error)` and `Error(Exception)`; these errors are outside that tuple. Existing fake backend coverage raises only `OSError`.

Impact: `reset_and_check` raises instead of returning bounded failed `Evidence`, contrary to its README/interface promise that backend connection exceptions fail through this interface. A normal connection/commit/snapshot failure can bypass a T016 consumer's failed-reset/evidence/quarantine branch and allow raw backend exception text to escape the bounded category boundary. This does not itself create a false successful reset, but it breaks the stable failure API at exactly the uncertain-reset boundary that must retain evidence and prohibit reuse.

Smallest useful fix: define and enforce a bounded backend-error conversion at the reset boundary, including the selected driver's operational failures. This can use explicit adapter exception normalization plus a documented enforced contract, or guarded backend calls; retain interrupts/cancellation behavior deliberately. Add fake-backend cases for failures from all three operations, including reset/commit acknowledgment uncertainty, asserting failed bounded evidence, no retry and no passing/reuse claim. No actual DB connection is required.

## Reviewed strengths and scope

- Fixed candidate was clean; all eight changed files are confined to `eval/grading/` and `eval/reset/`. Contracts, fixture bytes, Go/SQL/runner/dependency manifests remain unchanged.
- State grading is independent of model prose and Go billing calculations. Registration validates the frozen corpus and exact supplied task/fixture identity. Expected invoice money/dates/customer/item/quantity and write deltas come from frozen literal expectations/assertions, with unchanged seed tables and ledger/generated-ID relationships checked.
- Snapshot checks bind trusted run/attempt, stage, generation, sealed mapping and positive receipt, rejecting capture before acknowledged seal. The docs correctly require trusted capture and same-transaction mapping observation; local JSON validation is not claimed as real fence proof.
- Read-only state fingerprints are order-independent and require the unchanged seed. Answers and MCP-source successful read evidence are separate from database state. Replay checks retain original-state grading, equal application fingerprints, original saved response, task/config/request identity and shared budget anchors; lifecycle/process/budget gating remains explicitly T016's responsibility.
- Reset policy validates registered scope before mutation, requires literal True acknowledgment, revoked capabilities, sealed cleanup evidence and unchanged registry, then verifies canonical after-reset seed. Fake tests are explicitly distinguished from live DB semantics.

All failure reasons currently collapse to a function-level category (for example `grade_state_failed`). T016 must still distinguish valid wrong task state from invalid/unsettled/missing evidence before composing comparison eligibility; it must not treat every false state result as a model failure. This integration responsibility should be made explicit in the eventual composition and checked there.

## Evidence and limits

Review used read-only diff/source/contract inspection; only this report was written. The independent tester owns the 65-test run and adversarial execution checks, including the two probes requested above. No reviewer test result or successful live behavior is claimed. Re-review the repaired fixed revision and obtain independent regression results before approval.

Actual PostgreSQL transactions, snapshot isolation, grants, reset/commit behavior, fencing, lifecycle execution, containers and inference remain **UNRUN**. No approval for runtime operations or task completion is given.
