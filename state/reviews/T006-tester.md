# T006 independent tester report

Verdict: **FAIL** for frozen candidate `64faec8858ce2b4e5ef0b026f841008664c1cbc1`.
No P0 observed. P1 semantic defects below prevent contract acceptance. This is
independent of the expected absence of runtime evidence.

## Candidate and execution scope

- Source read only: `/home/sfkim/projects/mcpbench/.worktrees/T006/contracts`.
- Verified worktree HEAD against `state/candidates/T006-v1.json`; all 22 listed
  SHA-256 source hashes matched. Schema ID is
  `https://mcpbench.local/contracts/v1/schema.json`.
- Read AGENTS.md, agents/tester.md, both T006 context packs, accepted architecture,
  evaluation/security contracts, candidate README/protocol/schema/validator/tests.
- Used token-efficient-coding. No source/test edits, commits, package installation,
  network, DB, Docker, model, build, or application execution. Only this main-tree
  report was written. All Python commands used `PYTHONDONTWRITEBYTECODE=1`.
- No persistent tests added or changed; independent mutants ran from stdin.

## Observed commands and results

Working directory for commands below: `.worktrees/T006`.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest contracts.tests.test_contracts -v
PYTHONDONTWRITEBYTECODE=1 python3 -m contracts.validate Catalog contracts/v1/catalog.json
PYTHONDONTWRITEBYTECODE=1 python3 -m contracts.validate Task contracts/v1/task.example.json
```

Actual: **15/15 unit tests PASS** (`Ran 15 tests in 0.342s`, `OK`);
CLI outputs `VALID: Catalog` and `VALID: Task`, both exit 0. The unit suite executes
all 90 registered cases: 45 valid accepted and 45 invalid rejected, with six
input/output/error cases per named tool.

Additional `PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'` probes imported
`contracts.validate`, used deep copies of committed examples, and observed:

- **PASS** all 11 standalone major-object examples accepted with socket creation
  patched to raise; all 206 schema `$ref`s are registered local definition refs;
  unregistered external registry retrieval raises `NoSuchResource` without network.
- **PASS** independent duplicate-key, NaN, Infinity, numeric overflow-to-Infinity,
  surrogate, invalid UTF-8 and >1 MiB wire samples rejected.
- **PASS** leap second, >6 fractional UTC digits, timezone offset and invalid month
  rejected. Quantity wire forms `2.0`, `2e0`, `true`, `1001`, and `0` rejected.
  Duplicate invoice items rejected.
- **PASS** additional public request oracle field and event authorization field
  rejected. Unknown major version 2 rejected in AgentRequest, Task, RunManifest,
  Event. Float durations and ratios accepted in declared metric fields.
- **PASS** mutated snapshot total remains shape-valid under StrictValidator, but
  `validate("Snapshot", ...)` rejects its arithmetic inconsistency, demonstrating
  the required schema-versus-semantic distinction.
- **PASS** existing complete event example from EVALUATION_PLAN remains valid;
  its incomplete task projection is explicitly documented as incomplete.
- **PASS** canonical hash vector for `{"z":"Café","a":[1,true,null]}` is
  `5daf43031d869ecb4785ac7172a26fe3a1ba31a2c3cd57acade3d40fc4e05ad7`;
  supplied tests independently exercise key/seed order, changed payload/price,
  float rejection and manifest file hashes.
- **FAIL** accepted/rejected mutants are reproduced below.

## P1 findings and reproduction

Run this exact read-only reproduction in the candidate root. `ACCEPTED` denotes
an observed invalid contract that should reject; the final line demonstrates a
legitimate read-only outcome that is rejected.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
from contracts import validate as c
from copy import deepcopy

def example(name):
    return c.load_file(c.ROOT / "v1" / (name + ".example.json"))

def probe(label, name, value):
    try:
        c.validate(name, value)
    except c.ContractError as error:
        print(label, "REJECTED:", error)
    else:
        print(label, "ACCEPTED")

for key in ["original_assertions", "verification_assertions"]:
    s = example("evaluation-result")
    s[key][0]["pass"] = False
    probe("failed " + key, "EvaluationResult", s)

s = example("evaluation-result")
s["metrics"]["verifier_calls"] = 0
probe("replay PASS with zero calls", "EvaluationResult", s)

s = example("evaluation-result")
s.update(overall_status="failed", task_success=False)
unknown = ["agent_settlement_pass", "db_oracle_pass", "answer_pass",
           "verifier_settlement_pass", "replay_pass"]
for key in unknown:
    s[key] = None
s["null_reasons"] = {key: "settlement unknown" for key in unknown}
# cleanup_pass=True, comparison_valid=True, quarantined=False remain unchanged.
probe("unknown settlement permits cleanup/comparison", "EvaluationResult", s)

s = example("evaluation-result")
s.update(verifier_settlement_pass=None, replay_pass=None)
s["null_reasons"] = {
    "verifier_settlement_pass": "read-only task, verifier not applicable",
    "replay_pass": "read-only task, no invoice/key replay",
}
s["metrics"]["verifier_calls"] = 0
probe("successful read-only run", "EvaluationResult", s)
PY
```

1. **P1: failed assertions can coexist with task/overall PASS.** First two probes
   print `ACCEPTED`; task_success, comparison_valid, overall_status remain true,
   true, passed. `validate.py:298–326` derives success from headline booleans and
   ignores failed original/verification assertion records. This admits internally
   contradictory authoritative grading evidence. Aggregate verdict consistency
   must be enforced for both assertion sets; a failed assertion cannot be hidden
   behind PASS flags.

2. **P1: unknown settlement can claim safe cleanup and valid comparison.** Fourth
   probe prints `ACCEPTED`. The only unknown detector at `validate.py:306–308`
   depends on an explicitly supplied failure code or a *false* settlement flag.
   Null unknown settlement plus explicit null reasons bypasses quarantine and
   cleanup protections. Although overall PASS is rejected for null settlement,
   this accepted object still claims cleanup succeeded and admits a comparison
   without any known agent settlement. The validator must distinguish skipped
   verifier settlement from unknown settlement and reject cleanup/comparison
   unless applicable revocation/drain evidence is positive. No reset is allowed
   merely because an emitter omitted the redundant failure record.

3. **P1: complete replay is accepted with zero verifier calls.** Third probe
   prints `ACCEPTED` with replay_pass and overall_status still true/passed.
   `validate.py:326` checks only `verifier_calls <= 2`, while the protocol's passed
   draft replay requires both same-payload and changed-payload checks. A success
   summary must require evidence/counts consistent with both checks; zero calls
   cannot prove either.

4. **P1: read-only baseline has no truthful successful terminal result.** Final
   probe prints `REJECTED: smoke PASS lacks required safety evidence`. Task and
   final-answer schemas explicitly support read_only/read_result_ids and the
   ten-tool catalog includes reads, but EvaluationResult has no task-kind/replay-
   applicability discriminator and unconditionally requires replay/verifier
   settlement true for every passed result. Read-only tasks have no created
   invoice/idempotency binding to replay; they must not fabricate such evidence.
   Add an explicit, cross-validated applicability/terminal-state contract, keeping
   the draft smoke gate's mandatory replay and both fences intact.

## Additional observed contract gaps

These are lower-priority than the P1 gate failures, but should be resolved or
explicitly scoped before downstream consumers rely on the freeze.

- **P2 catalog identity/order:** both `cat=deepcopy(c.CATALOG);
  cat["tools"]=cat["tools"][:3]` and a copy with `cat["tools"].reverse()` are
  accepted by `validate("Catalog",cat)`, preserving the frozen baseline catalog
  ID/version. `_semantics("Catalog")` checks entries/uniqueness but not exact
  ten-tool membership/order. The committed artifact is correct; the validator
  does not enforce its advertised ordered baseline identity.
- **P2 retry taxonomy:** `validate("ToolError", {"code":"authorization_denied",
  "message":"denied","retryable":True})` is accepted. A ToolResult error with
  code idempotency_conflict and retryable true is also accepted. PROTOCOL explicitly
  prohibits retries for authorization/domain/conflict errors. ToolError needs a
  semantic/code constraint, applied through error envelopes as well as directly.
- **P2 read fixture consistency:** take task.example, set principal billing-reader,
  permitted/required/relevant tools to `["billing_get_customer"]`, expected_state
  to `{"kind":"read_only","required_record_ids":["MISSING"],
  "allowed_changed_tables":[]}`, final_answer_rule to read_result_ids. Calling
  `validate_task_fixture(task,fixture.example)` accepts the nonexistent expected
  record. Its pair validation currently checks seeded existence/prices only for
  draft_invoice; read-only expected IDs need a typed table/tool-aware fixture check.

## Acceptance mapping

| Criterion | Result | Evidence / limit |
| --- | --- | --- |
| Ten named tools, smoke3, input/output/error shapes | PASS artifact; FAIL full semantics | All tools/cases present; catalog identity/order and retry gaps above |
| Strict versioned loader, dates, lexical integers, unknown fields, bounded documents | PASS | Author and independent adversarial parsing/date/bound checks |
| Local-only schema references, IDs and deterministic hashes | PASS static | 206 local refs, offline registry refusal, pinned hashes/vector/schema derivation tests |
| Fixture/task/expected state arithmetic and smoke oracle | PASS draft; FAIL read completeness | Exact 25,000 cents retained, create-only required and three relevant tools; read-pair gap |
| Public request/result versus private auth/control mapping | PASS static | Closed envelopes, secret-key probes, separate AuthInput and immutable registered mapping |
| Run manifests, comparable budgets and four strategy IDs | PASS static | Pinned dependency record, explicit unavailable versions, fixed budgets; no ranking freeze |
| Typed events, grading/metrics, missing values and terminal validity | FAIL | Events/examples/null token handling pass; four P1 summary/result defects |
| Concrete fence/receipt/drain/replay/reset protocol | PASS normative; runtime UNRUN | Protocol includes the required invariants below; summary enforcement remains FAIL |
| Valid/invalid major objects and every tool; meaningful local tests | PASS supplied coverage; FAIL adversarial gate | 15 tests/90 cases/11 examples pass, independent counterexamples reproduced |
| Architectural/security boundary preserved | PASS static | Fixed launcher/evaluator/Go roles, narrow paths/env/args; no new runtime permission exercised |

## Protocol assessment and missing runtime evidence

The normative fence design follows the approved boundary: opaque 32-byte capability
outside model/public logs; immutable server-controlled run/schema routing; ACL on
all methods; shared run-row lock held for the whole tool transaction; exclusive
seal/drain followed by positive COMMIT acknowledgment before authoritative snapshot;
unknown means quarantine and no reset/reuse. Original state/answer/outcome success
precedes verifier capability. Verifier is a separate no-model mode, constrained to
existing invoice/key and never creates an absent invoice; exactly the two declared
checks, no retries, final seal before final snapshot/reset. The 30-second absolute
post-agent budget includes transport/snapshots/grading, each operation <=5 seconds,
and cannot rescue/extend the 300-second agent budget.

The PostgreSQL row-lock privilege caveat is explicitly addressed with UPDATE only
on an inert lock_marker column, no service UPDATE on state/capability/routing,
and a distinct read-only grader connection. Protocol documents no actual grants
or concurrency proof. Host launcher alone starts children; evaluator private DB
access, host-loopback Go agent/MCP, fixed endpoints, cleared env, read-only/narrow
mounts and separate auth files stay within the approved design. No actual security
boundary expansion requiring approval was observed. OpenTelemetry/Jaeger/dashboard,
retrieval implementations and ranking knobs remain deferred.

**UNRUN / prerequisite BLOCKED, expected for T006:** actual SQL grants/lock ordering,
concurrent drain and late-commit behavior, acknowledged/uncertain COMMIT handling,
credential/mount isolation, MCP negotiation/server ACL execution, real JSONL capture,
model behavior, resource monitoring, replay DB nonmutation and safe scoped reset.
These require admitted later T018–T023/T040 work; T001/T007 resource gates remain
blocked. No local JSON test is claimed as PostgreSQL/runtime evidence. Missing
runtime evidence is not the cause of this static FAIL.

The orchestrator owns integration/status changes. Candidate was not modified.
