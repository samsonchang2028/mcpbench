# T006 repair pass 1 — same approved architecture/security boundary

Read independent state/reviews/T006-reviewer-v1.md and T006-tester-v1.md in main.
Original source commit64faec8 is frozen history. Owner may now edit ONLY contracts/**
in .worktrees/T006. Do not edit main/docs/state or deploy grants, network, runtime.
No downstream work until independent re-review/re-test passes. Fix root causes
with regression vectors; don't merely weaken the tests or forbid legitimate failures.

## P1 outcome truth table

Freeze and enforce workflow applicability and coherent verdict relationships.
Passing original/verification assertions cannot contain pass=false; observed
verification_failed/settlement_unknown/cleanup/artifact failure cannot coexist with
overall PASS or controlled-comparison validity. Unknown settlement (including null
with unknown reason) cannot authorize cleanup, comparison validity, task PASS or
non-quarantine. Null reason values must be typed/meaningful, not free-form escapes.
Replay PASS needs actually performed two expected verifier calls and passing
verification assertions. Quarantine invalidates comparison and prevents reset.

Do NOT declare every model/tool failure an invalid comparison: normal wrong answers,
state_incorrect, bad arguments and timeouts remain valid measured failures if setup,
settlement, observability and cleanup are complete. Original task_success is independent
of later verification failure, but overall run gate/comparison then fails. Recoverable
agent errors followed by success need not automatically falsify original correctness;
separate terminal operational/safety failures from recovered reasoning/tool errors.
Specify truth table in protocol and regress exact independent counterexamples.

## P1 successful read-only lifecycle

ExpectedReadOnly already exists: add explicit workflow applicability in private
control/evaluation records and cross-validation to Task.expected_state.kind. Do
not leak grader expected kind/records/annotations into the model request.
Successful project/timesheet reads require original acknowledged settlement,
unchanged-state oracle, exact required record-ID answer, preserved final snapshot,
artifact/cleanup success. No invoice verifier is issued; replay/verifier settlement
are null with precise not-applicable reason, verifier calls0. Initial sealed registry
remains closed, so finalize safely reads final unchanged state/cleans up without
inventing a verifier fence. Original failure still gets retained/graded/cleaned only
after known settlement. Preserve FULL two-call/two-fence invoice smoke gate.
Read-only expected IDs must exist in referenced fixture; missing IDs reject.
Report any required O-owned clarification/example update to EVALUATION_PLAN; don't
silently weaken invoice invariants or edit docs outside your lane.

## P1 exact existing process transport

Add minimal closed/versioned typed control-phase request/result, host ProcessExit,
VerifierResult schemas plus positive/negative cases and identity/phase/deadline
cross-checks. Keep EXISTING process topology and CLI phases (prepare/grade/finalize
+ agent/verify); no new service or broad command authority. Specify bounded relative
artifact references and request/result delivery (complete/missing/partial/malformed/
oversized), exit/timeout/termination, next action skip/verify/finalize/quarantine.
Preserve run/attempt/task/config bindings, host-owned process exit (not agent claim),
and original/verification verdict separation. No token in these result/log messages.

One shared post-agent deadline/budget anchor spans grade→verify→finalize. Launcher
measures its total30s with its OWN monotonic clock and bounds every child/op by
min(5s,remaining); timestamps/anchor ID allow correlation, not comparing unrelated
producer monotonic origins. Phase restart must never mint a new30s budget. V1 can
fail closed/quarantine after launcher restart rather than implement new recovery.
Freeze deadline consistency/remaining-budget rules and validate chains statically;
no actual process/DB proof required until admitted gates.

## P1 typed JSONL evidence

Replace all-optional EventData with per-event required evidence. Add explicit
start/completed/failed/interrupted lifecycle support for model/tool/DB operations;
source/phase/call correlation, tool ID/arguments/result (or bounded immutable refs),
model counts/durations, retrieval exposed/authorized IDs and catalog/query/schema
hashes, fence receipt/generation, grading/assertions/failures, host process exit/
delivery. Every relevant started operation must close or have interrupted marker;
provide valid interrupted trace and missing-evidence negative tests. Don't claim a
stream invariant is validated by one-event shape validation. Minimal stream helper
for sequence/event uniqueness/correlation is appropriate; no logging runtime yet.
All fields must be reconstructible without secret/oracle leakage to model.

## Other independently found gaps

- Freeze baseline catalog identity/version/hash/order: a truncated smoke3 or reordered
  catalog may NOT reuse baseline ID/version; smoke is an authorized exposure subset,
  not a different global catalog. Later extensions remain new registered hashes.
- Authorization/validation/conflict/domain errors never retryable; constrain by code,
  including nested ToolResult. Bound transient error whitelist in protocol.
- Complete parse/UTC/integer/offline refs/canonicalization behavior and all original
  literal invoice expectations remain intact. Update manifest hashes/README.

Use installed libraries/local tests only. Add genuine reproductions for all findings.
Run tests/CLI/standalone examples, stage explicit source (no pyc), commit repair,
return hashes/checks plus any needed prose corrections, then pause.
