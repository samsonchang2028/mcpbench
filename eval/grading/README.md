# T010 offline snapshot oracle

This module grades only the frozen T009 development corpus. It imports no billing
implementation and derives no expected price or invoice total from server output.
`Task.expected_state` and `assertions.json` retain the independent **25000-cent**
expected draft. Registration verifies the immutable manifest/corpus and matches
input fixture/task objects against it. New datasets need an explicit reviewed
extension; they are rejected rather than silently interpreted.

From repository root with the existing locked T008 environment:

```sh
PYTHONDONTWRITEBYTECODE=1 /home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python -m unittest eval.grading.test_oracle eval.reset.test_contract contracts.tests.test_contracts eval.fixtures.test_fixtures -q
```

## Callable interface for T016

Import from `eval.grading`. All grade functions return immutable
`Evidence(passed: bool, reason: str)`. Invalid, missing, mismatched or unsupported
evidence returns false with a bounded category; no raw payload is echoed.
`RunScope(run_id, attempt_id, idempotency_key)` comes from trusted launcher state,
never from the snapshot or agent. Monetary values are integer cents; times are
contract UTC strings, and contract durations are milliseconds.

- `grade_state(task, fixture, assertions, snapshot, mapping, receipt, scope)`:
  DB state only. Requires an agent-only generation-1 snapshot, the corresponding
  sealed registered mapping, a positive agent fence and capture at/after commit.
  Checks all seed rows unchanged, exact write deltas, literal header/line values,
  generated ID references, ledger key and canonical original payload hash. Read
  tasks require the unchanged canonical seed, independent of row order.
- `grade_answer(task, snapshot, agent, scope)`: structured answer only. Requires a
  completed AgentResult and exact saved invoice ID or exact record ID set. Answer
  prose never supplies state evidence. Combine only with separately passing state.
- `grade_read_trace(task, events, scope)`: read evidence only. Requires a valid
  complete EventStream with matching trusted identity, execution-phase permitted
  reads and successful **MCP-source** relevant results containing every expected
  record ID (including references). Agent-reported counts or agent-only completion
  events are insufficient. This does not establish real server ACL enforcement.
  Safely denied unauthorized attempts stay in the complete stream and supply no
  read evidence. Their correlated failure must record an observed authorization
  denial or unauthorized attempt (and any tool error must be authorization denial).
  Successful unauthorized execution, unproven/interrupted denials and verifier
  tool activity fail even when a later authorized read succeeds.
- `grade_replay(task, fixture, assertions, agent_snapshot, agent_mapping,
  agent_receipt, final_snapshot, final_mapping, final_receipt, request, result,
  scope, config_hash)`: independent replay consistency. Requires original DB state,
  generation-2 final seal, equal application-state fingerprints, exact saved replay
  response, same key/invoice/request/task/config bindings, constrained conflict and
  two successful verifier checks. Request/result budget anchors must match.

T016 owns lifecycle ordering and final frozen `EvaluationResult` composition.
Persist original state, answer, budget and process verdicts **before** verifier
issuance. Call replay only after original state/answer/process/budget PASS; its
result cannot rescue original failure. Keep execution/state, answer, trace,
settlement, verification, setup/reset, logging and comparison verdicts separate.
Do not turn these local checks into lifecycle or live-model PASS. In particular,
process exits, actual byte/hash verification and shared elapsed-time accounting
remain the launcher's responsibility.

`mapping`, snapshots, receipts, traces, verifier messages and `config_hash` must
come from trusted captured control/server channels. Validate and persist their
actual artifact bytes. Mapping must be observed in the snapshot's read-only
repeatable-read transaction; a JSON object or test receipt does not prove that.
This module never opens a database connection, authenticates a caller, fabricates
a fence, captures a snapshot or executes verification.

## Validation boundary

Offline tests cover positive invoice/read cases and wrong customer/price/status/
dates/currency/item/quantity/total, missing/extra writes, seed mutation, stale/
wrong-run/unsealed snapshots, answer mismatch, incomplete trace and replay drift.
Schema-valid wrong customer/price and an additional complete valid invoice are
explicitly rejected, demonstrating that schema validity is insufficient.

Actual SQL snapshots, permissions, concurrent fencing, PostgreSQL reset, MCP reads,
replay execution and live-model behavior are **UNRUN until their admitted T018+
tasks**. No database, container, model, network or dependency install is used here.
