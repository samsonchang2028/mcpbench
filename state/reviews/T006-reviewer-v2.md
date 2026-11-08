# T006 independent re-review (v2)

Verdict: **CHANGES REQUIRED**. No P0 observed; two remaining P1 defects block the static contract freeze.

Reviewed frozen candidate `f18638770218147ff67c90c17df5f2037466efd7` in `.worktrees/T006`, with targeted diff from `64faec8858ce2b4e5ef0b026f841008664c1cbc1`. All **41 source hashes and 3 main-tree governance hashes** in `state/candidates/T006-v2.json` matched. Read the repair context, archived reviewer/tester counterexamples, updated main EVALUATION_PLAN clarification/event, changed validator/schema/protocol/tests and examples. Only this report was written.

## Remaining findings

1. **P1 — Actual unauthorized execution can remain comparison-valid.**
   `contracts/validate.py:337,378–387` uses `metrics.unauthorized_executions == 0` only to derive original task success. Once that makes the original fail, invoice verification is skipped correctly, but the comparison gate never checks actual unauthorized execution. Starting from the passing evaluation example, the following mutation is accepted:

   ```python
   s.update(task_success=False, overall_status="failed",
            replay_pass=None, verifier_settlement_pass=None)
   s["null_reasons"] = {"replay_pass": "original_failed",
                        "verifier_settlement_pass": "original_failed"}
   s["metrics"].update(unauthorized_executions=1, verifier_calls=0)
   s["verification_assertions"] = [r for r in s["verification_assertions"]
                                   if r["name"] == "unchanged-state"]
   validate("EvaluationResult", s)  # Accepted; comparison_valid is still true.
   ```

   This is an unsafe server permission violation, distinct from a denied selection attempt or ordinary failed agent task. Its results cannot support the controlled comparison/security gate. Add a zero-actual-unauthorized-execution condition to comparison validity, and test this exact failure path. Keep denied attempts and ordinary wrong answers/timeouts eligible for valid failed-task comparisons when all operational evidence is sound. No actual unauthorized runtime operation occurred in this review; this is a synthetic JSON counterexample.

2. **P1 — Host agent exit evidence is not bound to the original success decision.**
   `contracts/validate.py:592–610,624–625` validates agent ProcessExit shape and result-delivery consistency, but checks only `reaped` before accepting an original passing result and launching verification. The abnormal-exit/duration check is applied exclusively to the verifier. Each of these independent mutations to `control-chain.example.json` is accepted with `results[1].original_pass=true`, action `verify`, and the original successful finalize chain:

   - Set the host agent exit's `termination` to `timed_out` (its observed code remains zero).
   - Set its `exit_code` to 2.
   - Set its `duration_ms` to 300001.
   - Set its `result_delivery` to `missing` and `result_ref` to null, and remove `requests[1].inputs.agent_result`.

   Thus the statically checked phase chain can claim original success and issue the trusted verifier after a timeout, abnormal process exit or absent result. This contradicts the accepted no-timeout-rescue rule and the documented host-owned result/exit boundary. Require original_pass true to have complete delivered result, successful normal host exit and within-task-deadline execution; bind the actual result status where that record is cross-validated. Missing/malformed/partial/oversized result and timed-out/nonzero exits must force original failure (or quarantine where settlement/process termination is uncertain), while still allowing settled failed attempts to grade/clean up. Add mutations for all delivery states and abnormal exits, plus a legitimate failed-agent comparison regression. This is a missing static consistency check; no process runtime proof is being requested.

## Disposition of previous findings

- **V1 verdict/assertion/null/replay contradictions repaired for the reported cases.** Failed original/verification assertions, replay success with zero calls, failed replay labeled comparison-valid, quarantine labeled comparison-valid, and inconsistent/unknown settlement now reject. Typed null reasons, terminal/recovered failure disposition and exact original assertion binding improve the truth table. The supplied regression suite retains ordinary failed agent attempts as valid measured comparisons; finding 1 is a narrower remaining safety exception.
- **Read-only project/timesheet completion repaired.** Private workflow applicability is cross-bound to Task; read-only results use null invoice replay/verifier settlement with typed reasons and zero calls, acknowledged initial fence, unchanged final state, exact record IDs and safe cleanup. Both successful project and synthetic timesheet read bundle checks are present. Invoice replay remains two calls and both fences.
- **Control transport substantially repaired.** Closed versioned ControlRequest/Result, ProcessExit, VerifierResult, ArtifactRef and ControlChain now specify identity, phase, host delivery, original/verifier separation and a shared non-resettable 30-second launcher clock. Regressions cover restarted deadlines and unreaped processes. Finding 2 is the remaining host-success binding defect.
- **Typed JSONL evidence repaired.** Per-event required payloads replace the optional bag. Model/tool/DB start, completion, failure and interruption shapes, process exit, fence receipt, grading evidence, source/phase rules and complete-stream sequence/correlation/closure checking are implemented. Empty tool completion now rejects; the interrupted trace validates. Stream validation is explicitly distinguished from individual event validation and runtime evidence.
- **Catalog/retry/read-ID gaps repaired.** Frozen baseline catalog identity/version/order is enforced; truncated and reordered catalogs reject. Authorization/domain/conflict errors cannot declare retryability, including nested tool errors. Expected read record IDs are typed by table and checked against fixture contents.

## Acceptance and observed evidence

- Exact ten tools and smoke3, 25,000-cent oracle, two units at 12,500 cents, fixed dates/draft-only behavior, create-only required set and optional relevant lists remain intact.
- Separate secret capability delivery, immutable registry routing, server ACLs, whole-transaction shared lock, exclusive acknowledged seal/drain, inert-column row-lock privilege caveat, no-repair verifier branch, original/final snapshots and quarantine/no-reset behavior remain documented within the approved architecture.
- Host-only launch privileges, narrow file/env/command/endpoints, Python private DB evaluator versus Go host-loopback agent/MCP, all four strategies and fixed budgets remain intact. No new security boundary, ranking implementation, retrieval engine or observability service was introduced.
- Strict local parsing, canonical hashes, offline references, integer money/quantity, float durations/ratios and missing-metric nulls remain covered. Public AgentRequest is unchanged and still excludes oracle/relevance annotations; new workflow/control data stays private.
- Updated main EVALUATION_PLAN read-only/comparison clarification is consistent with the repaired workflow; its expanded complete tool event validates against the candidate schema. The task projection remains explicitly partial.

Commands/observations (all Python used `PYTHONDONTWRITEBYTECODE=1`):

- `git rev-parse HEAD`: exact frozen v2 commit above.
- Local SHA-256 verifier: **41/41 source and 3/3 governance hashes match**.
- `python3 -m unittest contracts.tests.test_contracts -q`: **27 tests PASS**, including 110 registered cases and the repaired workflow/control/event regressions.
- Direct validation of all manifest-listed standalone examples: **30/30 PASS**.
- Independent old-case mutations: failed original assertion, failed verification assertion, zero replay calls, failed replay comparison, quarantined comparison, reordered/truncated catalog, retryable denial, empty tool completion: **all rejected**.
- Independent new mutations: unauthorized-execution comparison and all four abnormal/missing agent-host outcome chains above: **unexpectedly accepted**, as documented.
- Updated main documentation event: **PASS**.

Database grants, real lock/drain/late-commit behavior, filesystem/mount and process enforcement, MCP lifecycle/server execution, reset and live model behavior are **UNRUN**, deliberately deferred to admitted integration tasks. Runtime absence is expected and is not the cause of this verdict. No network, DB, Docker, model, install, build, runtime or source edits occurred. No downstream execution or gate bypass is authorized by this report.
