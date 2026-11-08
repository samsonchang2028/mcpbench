# T006 independent review

Verdict: **CHANGES REQUIRED**.

Reviewed frozen candidate `64faec8858ce2b4e5ef0b026f841008664c1cbc1`
in `/home/sfkim/projects/mcpbench/.worktrees/T006`, against candidate manifest
`state/candidates/T006-v1.json`. All 22 recorded source hashes matched. No source
files were edited. Applicable reviewer and token-efficient-coding instructions
were used. This review covers contracts, not runtime acceptance.

## Findings

1. **P1 — Evaluation validation admits contradictory PASS and comparison claims.**
   `contracts/validate.py:298–326` only checks selected aggregate booleans and checks
   the full gate when `overall_status == passed`. Independently reproduced:
   (a) the passing example with `overall_status=failed,replay_pass=false` still
   validates with `comparison_valid=true`; (b) a passing example with an original
   assertion `pass=false` still validates as passed; (c) adding an observed
   `verification_failed` failure still validates as passed; (d) changing to
   `overall_status=failed,quarantined=true` still validates with comparison validity
   true. These conflict with the accepted rule that verification failure invalidates
   comparison and that retained assertions/failures determine the verdict. An
   independent reader cannot tell which contradictory evidence is authoritative.
   Define and enforce a coherent truth table across outcome, applicability,
   assertions, failure classes, quarantine and comparison validity. Do not simply
   exclude every failed agent task: valid comparisons must retain legitimate agent
   failures. Add regression cases for these accepted contradictions.

2. **P1 — Read-only baseline tasks have no successful terminal workflow.**
   `contracts/v1/schema.json:1401` provides `ExpectedReadOnly`, but
   `contracts/validate.py:324–326` requires replay and verifier settlement true for
   every overall PASS. `VerificationRequest` at schema line 2359 requires an
   invoice, create arguments and two draft checks; `PROTOCOL.md:175–193` only
   describes that invoice verifier or skipping verification on original failure.
   A successful reader project/timesheet query has no invoice to verify, and its
   honest null replay/verifier-settlement flags (with reasons) are rejected as an
   overall PASS. Reproduced by changing these two flags to null on the passing
   evaluation example and adding the corresponding read-only reasons: rejected
   with `smoke PASS lacks required safety evidence`. This blocks the required
   ten-tool project/timesheet baseline despite valid Task/read schemas. Freeze an
   explicit read-only lifecycle/applicability discriminator, with original read
   answer and unchanged-state checks, acknowledged settlement and safe cleanup;
   preserve the full two-call/two-fence invoice smoke gate. Add positive and
   negative end-to-end read-only contract examples. Resolve any necessary prose
   clarification through the orchestrator rather than silently weakening the
   accepted invoice gate.

3. **P1 — Claimed typed launcher/evaluator/verifier transport is not frozen.**
   `contracts/PROTOCOL.md:40–51` names a private control request, typed phase
   decisions/results, skip/quarantine decisions and verifier exit/result consumed
   by finalize. No named schemas define those requests/results or their bounded
   paths, exit delivery/termination status, phase identities, or shared absolute
   post-agent deadline. `AgentResult` has model/tool counts and final answer;
   `EvaluationResult` is a terminal grading summary; neither specifies these
   phase messages, and no verifier result exists. The three processes therefore
   cannot implement the claimed frozen interface without inventing critical
   control fields in downstream tasks, including how finalize distinguishes a
   completed verifier from a missing/partial/crashed one and how phase restarts
   retain the same 30-second deadline. Add minimal closed, versioned phase request/
   result and verifier result/exit schemas with valid/invalid examples and identity/
   phase/deadline consistency checks. This needs no DB or process runtime proof.

4. **P1 — JSONL schema does not require evidence for its event types and cannot
   represent the required operation lifecycle.**
   `contracts/v1/schema.json:2489,2650` gives every event the same entirely optional
   `EventData` bag. `contracts/validate.py:288–297` only requires call IDs for three
   event types. Replacing the passing `tool.completed` example's data with `{}`
   validates, losing even tool identity/outcome. A `fence.completed` event likewise
   needs no receipt/generation, and grading/failure events need no assertions or
   failure. The event enum has no model/tool start or interrupted-operation event;
   data has no launcher exit code/termination/delivery fields or typed DB operation
   identity. Accepted EVALUATION_PLAN requires every start to close or be explicitly
   interrupted, and TASK_GRAPH T017 requires correlated MCP/DB events. Empty
   completion records cannot reconstruct interrupted work or support attribution.
   Use event-type-specific required payloads, explicit start/termination support
   and source/phase/correlation rules (or an equivalently precise minimal schema),
   with negative cases for missing evidence and valid interrupted traces.

5. **P2 — Retryability contradicts the stated error taxonomy.**
   `contracts/v1/schema.json:849` accepts `ToolError` with
   `code=authorization_denied,retryable=true`; independently validated. The protocol
   says authorization/domain/validation/conflict failures are never retryable.
   Constrain retryable by error code, including nested `ToolResult` errors, and
   document which bounded transport/DB failures can set it true.

## Acceptance mapping and positive evidence

- Ten named tools and exact three-tool smoke subset: present, bounded argument/
  result/error definitions and server ACL design; tests cover all ten.
- Exact smoke oracle: preserved at 25,000 cents, quantity two, 12,500-cent price,
  correct dates/draft status, create-only required set and optional relevant lists.
- Public/secret boundary: `AgentRequest` excludes oracle/relevance annotations;
  separate private `AuthInput`, opaque capability, trusted registry/schema mapping,
  allowlisted endpoints, narrow mounts/env, controller-only launches are documented.
  No actual secrets or architecture expansion identified.
- Fence design: shared lock spans each transaction; exclusive seal drains and
  revokes with positive COMMIT acknowledgment; READ COMMITTED and inert-column
  UPDATE privilege caveat are addressed. Unknown settlement quarantines without
  reset; verifier branch cannot INSERT or repair an absent invoice. Original
  snapshot/verdict precedes verification, then final seal/snapshot. Invoice budgets
  remain 300 seconds plus a separate total 30 seconds, five seconds per operation,
  two verifier calls and no retries.
- Strict parser/canonicalization: duplicate keys, nonfinite numbers, invalid UTF-8,
  nesting, dates, strict lexical integer fields, unknown fields, local-only refs,
  canonical hashes and snapshot money/reference consistency are implemented and
  tested. Float duration/ratio fields and null missing metrics are retained.
- Four strategies preserved; ranking settings deferred; no retrieval engine,
  OpenTelemetry/Jaeger/dashboard, runtime implementation or unrelated source added.
- Fixture/task and partial documentation examples are explicitly distinguished;
  existing identifier and event example compatibility is retained.
- Overall acceptance is incomplete due to findings 1–4, especially workflow and
  trace/result consistency. Existing passing examples do not exercise these gaps.

## Observed checks and remaining evidence

Ran only local read-only Git/Python inspection with Python bytecode disabled:

- `git -C .worktrees/T006 rev-parse HEAD`: exact reviewed commit above.
- Python SHA-256 verification of candidate manifest: 22 files matched, zero
  mismatches.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest contracts.tests.test_contracts -q`
  from candidate root: **15 tests passed**. This includes 90 named cases, tool
  coverage, offline reference guard, manifest hashes and parser/semantic checks.
- Independent Python mutations: reproduced all accepted/rejected cases described
  above; no files created by those experiments.

Runtime DB grants, locking/concurrency/late commits, MCP negotiation, mount/launch
permissions, reset, live model support and performance are **UNRUN**, as required
while resource/runtime gates remain unresolved. This is not itself a T006 failure;
actual proofs belong to admitted later tasks. No network, database, Docker, model,
package install or source changes were performed. Approval, when obtained later,
does not authorize bypassing those gates or marking runtime tasks complete.
