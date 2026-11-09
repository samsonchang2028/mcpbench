# T016 focused independent re-review

Candidate: `06ccb00fcc54fa8c609b8bf4a18e97718603fb6a`, clean frozen `.worktrees/T016`; repair diff against `300a76122b75ab6522a6cc832baa892fe5642bfe`. Reviewed all four changed files and the affected budget/backend call paths, with targeted checks of the production T018 factory and frozen budget semantics.

Verdict: **APPROVE**. No remaining P0/P1 identified in this focused source re-review. This supersedes the two open findings in `T016-reviewer.md` for this candidate.

## Findings resolved

- **Production backend factory argument:** `eval/runner/__main__.py` now supplies the fixed pathname as an exact `str`, matching the production factory's exact-type and fixed-path requirements. The replacement test double enforces both constraints, so the previous incompatible Path call would fail the regression.
- **Absolute post-agent deadline:** `Budget.observation()` now takes the greater of continued monotonic elapsed time and the elapsed floor implied by the immutable absolute UTC deadline. Remaining time and each operation timeout consequently shrink before absolute expiry even when the incoming launcher observation is stale. Each accepted floor carries forward with local monotonic deltas; a later backward UTC change cannot restore time. Upward rounding prevents a positive submillisecond remainder from granting another millisecond of IO. Existing anchor identity and observed overruns remain preserved.

The new regression cases cover unchanged anchor/operation cap behavior, a stale observation one second before expiry, forward/backward wall-clock changes, expiry during an operation with rejection of its acknowledgment and subsequent IO, refreshed bounds across reset calls, and reset blocked before backend IO when already expired. `Evaluator.operation` applies the budget before dispatch and checks again after return; `BoundedBackend` retains separate checks for each reset operation. The repair keeps the fixed transport, private output layout, and backend responsibilities unchanged. README language accurately distinguishes conservative budget accounting from latency measurement.

## Evidence and limits

This lane performed source/diff review only: no tests, SQL, database connections, Docker/model requests, installation, source edits or Git mutations. Root owns independent test reproduction. The author's reported 151-test result with nine explicit PostgreSQL skips, and the parent's report of passing real T018 lifecycle evidence, were supplied context rather than checks executed by this reviewer.

Production driver cancellation, trusted launcher transport/clock enforcement, actual private mounts, and full-stack telemetry remain outside this focused repair review. The original review's unchanged-path observations and operational limitations still apply. Approval does not authorize workload startup or establish completion of later integration gates.
