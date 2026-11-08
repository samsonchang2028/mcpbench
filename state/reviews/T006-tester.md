# T006 independent tester — frozen v3

Verdict: **PASS for the T006 static contract gate**. No unresolved P0/P1 found in
the observed checks. This is not runtime admission or proof of DB/process behavior.

## Candidate identity and scope

Candidate `32bafe0607bfb81938d151de6c15e8288e9bc526`, source read only in
`/home/sfkim/projects/mcpbench/.worktrees/T006/contracts`.
Verified HEAD and all **41 source hashes** in `state/candidates/T006-v3.json`;
verified its **3 governance hashes** against MAIN ARCHITECTURE, EVALUATION_PLAN
and SECURITY_RESOURCE_CONTRACT. Rechecked source hashes unchanged after testing.
V1/v2 reports are archived separately; this report assesses only v3.

Read the narrow v2→v3 validator, schema, protocol, README, examples and tests diff,
using existing AGENTS/tester/context instructions and token-efficient-coding.
Only this main-tree report was written. No candidate source/test edits or commits,
network, packages, runtime services, DB, Docker, model, build or subagents.
All Python commands used `PYTHONDONTWRITEBYTECODE=1`.

## Executed checks

From the candidate root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest contracts.tests.test_contracts -v
```

Actual: **32/32 PASS**, `Ran 32 tests in 2.221s`, `OK`. Suite executes all **118**
registered cases and retains six input/output/error cases for each of the ten tools.

Executed all registered CLI examples through the following loop in a
`PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'` probe:

```python
manifest = c.load_file(c.ROOT / "manifest.json")
for row in manifest["examples"]:
    result = subprocess.run(
        [sys.executable, "-m", "contracts.validate", row["contract"],
         str(c.ROOT / row["file"])], capture_output=True, text=True)
    assert result.returncode == 0, (row, result.stderr)
```

Actual: **30/30 CLI examples PASS**. Independently validated all 30 examples with
socket creation patched to raise: **PASS offline**. Checked all **313** `$ref`s
target known local definitions; unregistered HTTPS registry lookup raises
`NoSuchResource` with sockets forbidden. Schema ID remains
`https://mcpbench.local/contracts/v1/schema.json`.

## Independent repair and adversarial evidence

Executed an stdin-only matrix independent of the author test methods:
**95 checks PASS: 44 expected rejections and 51 expected acceptances**. No invalid
acceptance or unexpected rejection occurred. Both draft_invoice and read_only
ControlChains were exercised.

| Probe / expected behavior | Actual |
| --- | --- |
| Exact v2 agent exit_code=1, timed_out, SIGTERM and duration_ms=300001 mutants cannot preserve original PASS or launch verifier | PASS: reject |
| Exact v2 summary task_latency_ms=300001 with passing budget/overall PASS | PASS: reject |
| Exact v2 failed-original summary with unauthorized_executions=1 and comparison_valid=true | PASS: reject |
| Exact prior-phase ArtifactRef hash mismatch; also path/byte mismatches at both phase dependencies | PASS: reject |
| Additional timed_out-with-code-0 and exit_code=255 variants | PASS: reject success; accept otherwise safe failed-original path |
| Missing, partial, malformed, oversized agent delivery with parsed result absent | PASS: reject original success; accept safe failed outcome |
| Parsed AgentResult failed, timeout or interrupted despite normal host exit | PASS: reject original success; accept failed-original path |
| Parsed model/tool/retry counts at 8/12/1 | PASS: accept |
| Counts one above 8/12/1 | PASS: reject original success; accept measured failed path |
| Host duration exactly 300000 ms | PASS: accept |
| Unreaped agent, including failed-original chain | PASS: reject advancement |
| Successful security quarantine with count retained, terminal unauthorized_execution, no cleanup and invalid comparison | PASS: accept |
| Recovered denied unauthorized_attempt with zero actual executions, both workflows | PASS: accept |
| Measured latency 299999 or 300000 ms with success, both workflows | PASS: accept |
| Known overrun represented as failed read-only outcome, budget false, safely settled/cleaned comparison | PASS: accept |
| Ordinary failed-agent evaluation with valid comparison and skipped verifier | PASS: accept |

These directly close all six P1 probe outcomes and the P2 structural mismatch from
v2. Changed observations are retained rather than clipped. A failed task remains a
valid measured comparison when settled, complete and safe; actual unauthorized
execution triggers the stricter safety stop independently of original correctness.

Executed a second independent stdin probe with **57 expected rejection checks**
covering preserved behavior, all PASS:

- Duplicate and nested duplicate keys, NaN/±Infinity, numeric overflow to Infinity,
  invalid UTF-8, Unicode surrogate, >1 MiB and excessive nesting.
- Quantity wire 2.0/2e0/boolean/string/zero/1001, injected money/routing/URL/key
  fields; UTC leap second/excess precision/offset/impossible date.
- Major version 2 in four public envelopes, oracle/database URL exposure in
  AgentRequest, capability field in Event.
- Failed original/verification assertions, zero-call replay, truncated/reordered
  catalog, retryable authorization/conflict errors.
- False or over-time fence receipts, restarted/regressing shared deadline,
  zero-check completed verifier, event closure loss/sequence gap/duplicate ID/
  bad interruption correlation, empty typed tool/model/DB/grading/fence/process
  event evidence.

Further observed PASS checks:

- Exact successful read task/fixture/mapping/evaluation/agent bundle validated;
  nonexistent required read ID rejected against seed.
- Float durations/ratios accepted where declared; replacing unavailable prompt
  total with an invented count rejected.
- A snapshot with inconsistent invoice arithmetic remains shape-valid but full
  semantic validation rejects it.
- Canonical hash vector for `{"z":"Café","a":[1,true,null]}` remains
  `5daf43031d869ecb4785ac7172a26fe3a1ba31a2c3cd57acade3d40fc4e05ad7`;
  independently reversing seeded rows preserves seed_hash.
- Supplied suite again exercises internally aligned unknown settlement without
  redundant failure record: unsafe cleanup/comparison reject; truthful quarantine
  with null cleanup/final-state verdicts accepts. Fence uncertainty never authorizes
  reset through the JSON terminal-state contract.

No persistent tests were added. Independent scripts used copied examples, local
validation and assertions; any unexpected acceptance/rejection would abort.

## Acceptance mapping

| T006 criterion | Result | Evidence and boundary |
| --- | --- | --- |
| Ten tools plus smoke3, inputs/outputs/errors/permissions | PASS static | Ten-tool cases, exact catalog membership/order, retry taxonomy and ACL contracts |
| Versioned strict wire parsing and IDs/bounds/dates/integer money/quantity | PASS | Supplied and independent malformed/boundary probes |
| Local-only refs, schema identity, canonical hashes | PASS | 313 refs, offline registry refusal, frozen hashes and stable vectors |
| Fixture/task/expected state and exact 25000-cent oracle | PASS static | Server-price/quantity arithmetic, immutable seed, required create-only versus optional relevant lists, read fixture/table binding |
| Public/private request, auth, mapping and manifest boundary | PASS static | Closed envelopes, separate secret AuthInput, registered schema derivation and version annotations |
| Typed phase/verifier/process transport and deadlines | PASS static | Trusted host outcome plus parsed status/count binding, shared deadline and prior ArtifactRef equality matrix |
| Typed JSONL and complete trace semantics | PASS static | Required per-event evidence, correlation, sequence, closure and interruption checks |
| Summary/task/comparison validity and missing metrics | PASS static | Prior false-PASS/unknown/unauthorized/budget counterexamples reject; legitimate failed/read outcomes accept |
| Normative fence/drain/replay/reset safety protocol | PASS design | Required lock/commit/snapshot/verifier/reset order retained; DB proof deferred |
| Four strategies, equal budgets and v1 exclusions | PASS static | Existing identifiers/budgets preserved; no ranking/retrieval/OTel expansion |
| Major object/tool examples and meaningful deterministic checks | PASS | 32 tests, 118 cases, 30 CLI examples and independent adversarial matrices |

## Runtime and security limitations

No actual runtime evidence is implied. Normative protocol retains the approved
trusted host launcher, private Python evaluator/DB and Go agent/MCP split; fixed
commands/env/loopback targets and narrow mounts; opaque capability outside model/
public logs; immutable server routing and ACLs. Whole-transaction shared fences,
exclusive seal/drain with positive COMMIT acknowledgment, quarantine/no reset on
uncertainty, original snapshot/verdict before verifier, existing-invoice-only replay,
<=2 calls/no retries, second fence and final unchanged snapshot remain explicit.
The PostgreSQL row-lock privilege caveat remains covered by inert-column-only
UPDATE, no service state/capability/routing mutation, and separate read-only grading.
The 30-second post-agent absolute deadline and <=5-second operations do not extend
the agent's 300-second budget.

Metadata equality establishes only consistency of supplied JSON. It does not prove
producer authenticity, actual paths/symlink handling, file bytes/counts/hashes,
credential/mount isolation, process execution or SQL settlement. Examples contain
synthetic artifact references; no hash test authenticates an external file here.

**UNRUN / prerequisite BLOCKED as expected for this task:** actual PostgreSQL grants,
locking/concurrency, late/unknown COMMIT, real read-only grader, replay nonmutation,
process/mount/credential isolation, real transport capture/deadlines, MCP lifecycle/
ACL execution, live model calls, resource monitoring and safe scoped resets. These
remain admitted T018–T023/T040 obligations; T001/T007 are not bypassed. No security
or deployment permission expansion was exercised, and no downstream task started.

Orchestrator owns integration and task status. Candidate source remains unchanged.
