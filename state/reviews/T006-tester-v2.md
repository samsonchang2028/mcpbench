# T006 independent tester — frozen v2

Verdict: **FAIL**. Candidate `f18638770218147ff67c90c17df5f2037466efd7`
fixes the v1 counterexamples but retains independently reproduced P1 safety and
deadline consistency gaps. No P0 observed. Runtime absence is expected and is not
the cause of this static-task FAIL.

## Identity and scope

Verified candidate HEAD and all **41 contract source hashes** in
`state/candidates/T006-v2.json`; verified its **3 governance hashes** against MAIN
EVALUATION_PLAN, ARCHITECTURE and SECURITY_RESOURCE_CONTRACT. Source inspected in
`.worktrees/T006/contracts`, read only. Read the validator changes, new schemas,
protocol sections, examples, tests and main evaluation clarification/event example.
The v1 report is archived as `state/reviews/T006-tester-v1.md`.

Only this report was written. No source or test changes, commits, packages,
network, runtime services, DB, Docker, builds, or models. All Python invocations
used `PYTHONDONTWRITEBYTECODE=1`; independent mutants ran from stdin. Rechecked all
41 candidate source hashes unchanged after testing. Token-efficient-coding used.

## Commands and observed results

From `/home/sfkim/projects/mcpbench/.worktrees/T006`:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest contracts.tests.test_contracts -v
```

Observed **27/27 PASS**, `Ran 27 tests in 1.124s`, `OK`. This executes all **110**
registered positive/adversarial cases, ten-tool input/output/error coverage,
canonical hashes, shape/semantic checks, mappings, examples, lifecycle streams,
read workflow and transport tests.

The following loop was executed from a `PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'`
stdin probe, with imports `subprocess, sys` and `contracts.validate as c`:

```python
manifest = c.load_file(c.ROOT / "manifest.json")
for row in manifest["examples"]:
    result = subprocess.run(
        [sys.executable, "-m", "contracts.validate", row["contract"],
         str(c.ROOT / row["file"])], text=True, capture_output=True)
    assert result.returncode == 0, (row, result.stderr)
```

Observed **30/30 CLI example invocations PASS**. Separately validated those same
30 examples with `socket.socket` patched to raise: **PASS offline**.

Independent stdin probes also observed:

- **PASS** all **312** schema refs target known local `$defs`; external registry
  lookup rejects with `NoSuchResource` while sockets are forbidden. Schema ID
  remains `https://mcpbench.local/contracts/v1/schema.json`.
- **PASS** eight additional duplicate-key/nonfinite/UTF-8/surrogate/size/depth
  wire samples rejected. Independent UTC leap-second, excessive fractional
  precision, offset and impossible-date samples rejected. Quantities 2.0, true,
  string 2, zero and 1001 rejected; author suite retains lexical/exponent tests.
- **PASS** public request oracle and database_url fields rejected. Existing strict
  versions, references, money, array limits and budget tests all pass.
- **PASS** a shape-valid snapshot with inconsistent invoice total rejects under
  full validation; canonical hash vector for `{"z":"Café","a":[1,true,null]}`
  remains `5daf43031d869ecb4785ac7172a26fe3a1ba31a2c3cd57acade3d40fc4e05ad7`.
- **PASS** prior failed original/verification assertions, zero-call replay,
  truncated/reordered catalogs, retryable authorization/conflict envelopes and
  nonexistent read fixture IDs all now reject.
- **PASS** exact successful read-only task/fixture/mapping/evaluation/agent bundle;
  legitimate failed-agent evaluation remains comparison-valid with no verifier;
  missing-result failed-agent ControlChain accepted as a measured failure.
- **PASS** a fully internally aligned unknown-settlement summary with cleanup and
  comparison still true rejects. Changing it to quarantine, null cleanup/final
  state, no verification assertions and invalid comparison accepts even without
  a redundant failure record. This directly rechecks the prior unknown loophole.
- **PASS** restarted/regressing deadline, zero-check completed verifier and false
  fence acknowledgment mutants reject. EventStream open-operation loss, duplicate
  event ID, source sequence gap and wrong interruption correlation reject.
  Empty tool/model/DB/grading/fence/process payloads reject as typed evidence.
- **FAIL** counterexamples below are accepted despite contradictory trusted facts.

## P1 reproductions

This exact read-only script reproduces the new defects in the candidate root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
from contracts import validate as c

def example(name):
    return c.load_file(c.ROOT / "v1" / (name + ".example.json"))

def probe(label, contract, value):
    try:
        c.validate(contract, value)
    except c.ContractError as error:
        print(label, "REJECTED", error)
    else:
        print(label, "ACCEPTED")

for change in [
    {"exit_code": 1},
    {"termination": "timed_out"},
    {"termination": "terminated", "exit_code": None, "signal": "SIGTERM"},
    {"duration_ms": 300001},
]:
    chain = example("control-chain")
    agent_exit = next(x for x in chain["exits"] if x["child"] == "agent")
    agent_exit.update(change)
    probe("original PASS despite " + str(change), "ControlChain", chain)

summary = example("evaluation-result")
summary["metrics"].update(task_latency_ms=300001, lifecycle_latency_ms=300500)
probe("PASS with measured task budget overrun", "EvaluationResult", summary)

summary = example("evaluation-result")
summary.update(task_success=False, overall_status="failed",
               db_oracle_pass=False, answer_pass=False,
               verifier_settlement_pass=None, replay_pass=None)
summary["null_reasons"] = {"verifier_settlement_pass": "original_failed",
                           "replay_pass": "original_failed"}
summary["original_assertions"] = [
    {"name": name, "pass": False, "reason": "Incorrect state/answer."}
    for name in ["db-oracle", "answer"]]
summary["verification_assertions"] = [
    row for row in summary["verification_assertions"]
    if row["name"] == "unchanged-state"]
summary["metrics"].update(verifier_calls=0, unauthorized_executions=1)
# comparison_valid remains True, cleanup known successful, state unchanged.
probe("unsafe failed attempt admitted to comparison", "EvaluationResult", summary)
PY
```

Actual: **all six probes print ACCEPTED**. Expected: each must reject the claimed
advancement, PASS, or comparison validity; retain the observed host/metric data and
represent a legitimate failure instead.

1. **P1 — ControlChain ignores failed/late agent host outcome when authorizing
   verifier.** `validate_control_chain` validates host agent ProcessExit shape,
   result delivery and `reaped`; only the *verifier* branch checks normal exit/
   zero code/time limit. A chain with original_pass true, action verify and final
   complete remains valid after agent exit_code 1, timeout, signal termination,
   or observed duration 300001 ms. Normative PROTOCOL explicitly says complete
   delivery cannot convert nonzero exit into success and requires original
   within-budget success before verifier. Bind these trusted host facts to the
   original verdict/allowed transition; a failed original may still settle and
   safely finalize without verifier. This is a pure JSON semantic defect, not a
   missing real-process experiment.

2. **P1 — reported agent budget and measured latency can contradict PASS.**
   EvaluationResult uses `agent_budget_pass=True` without checking a present
   task_latency_ms against the fixed 300000-ms budget. The fifth probe still has
   task_success true, comparison_valid true, overall_status passed with measured
   task latency 300001 ms. Do not clip/drop observations; enforce consistency and
   fail original task success on known overrun. The analogous host-duration
   counterexample in finding 1 demonstrates this at the transport boundary too.

3. **P1 — unauthorized execution can remain a valid comparison after original
   failure.** Setting unauthorized_executions to 1 makes original success false,
   but the comparison_valid safety predicate never checks that metric. A properly
   settled and cleaned failed-agent result is allowed as a controlled comparison;
   actual unauthorized execution is outside comparable permissions and must
   invalidate comparison independently of whether task_success was already false.
   Do not conflate a denied unauthorized *attempt* with actual execution.

## Structural reference consistency versus deferred byte proof

**P2 observed:** `ControlChain` accepts a next-phase `prior_phase_result` reference
that disagrees with the previous evaluator's complete-delivery `result_ref`, even
though both objects are present and identify the same prior message:

```python
chain = example("control-chain")
chain["requests"][1]["inputs"]["prior_phase_result"]["sha256"] = "f" * 64
previous = next(x for x in chain["exits"]
                if x["child"] == "evaluator" and x["phase"] == "prepare")
assert chain["requests"][1]["inputs"]["prior_phase_result"] != previous["result_ref"]
c.validate("ControlChain", chain)  # Observed accepted.
```

This equality is checkable from the supplied JSON records. Existing checks bind
prior_result_id/message IDs, but not these two representations of the same artifact.
The helper should either enforce equality or state that limited scope explicitly.

Other mutated agent_exit/final-result reference hashes were also accepted. There
is no corresponding self-reference/raw file byte input in the chain object from
which to establish those hashes; their acceptance is **not** claimed as proof of
an actual wrong file being consumed. PROTOCOL explicitly requires actual path,
symlink, byte count and hash verification in future loading code. Those checks,
mount protections and source authenticity are **UNRUN**, separate from the
purely structural equality above.

## Acceptance mapping

| Criterion | Result | Evidence / remaining gap |
| --- | --- | --- |
| Ten tools, smoke subset, inputs/outputs/errors/ACL contracts | PASS static | Full case coverage; exact catalog order and retry taxonomy repairs pass |
| Strict wire parser/version/date/integer/unknown-field bounds | PASS | Existing and independent parser/format/size checks |
| Offline refs, registered IDs, canonical hashes | PASS static | 312 local refs, offline rejection, frozen hashes and stable hash vector |
| Fixture/task/expected state, exact 25000-cent oracle | PASS static | Draft oracle retained; required create-only vs optional lists; typed read-table fixture validation |
| Read-only success and legitimate failed comparison | PASS ordinary cases; FAIL unsafe comparison | Successful read bundle and measured failed-agent path pass; unauthorized metric loophole |
| Public/private envelopes and trusted schema mapping | PASS static | Closed fields, separate auth/control, schema derivation and phase checks |
| Typed phase/exit/verifier transport and shared deadline | FAIL | New transport shapes and regression examples pass; host outcome/latency contradiction plus ref consistency gap |
| Typed events and complete operation streams | PASS static | Required evidence, lifecycle closure/correlation, null token availability tests |
| Summary grading, terminal status and safety validity | FAIL | Prior assertion/unknown/replay repairs pass; known budget and unauthorized-comparison gaps |
| Normative fence/drain/replay/reset protocol | PASS design | Required invariants present; actual SQL/runtime proof UNRUN |
| Four strategy IDs, equal budgets, v1 scope | PASS static | Existing budgets/strategy definitions retained; no retrieval engine/ranking or OTel expansion |
| Valid/invalid examples and deterministic checks | PASS supplied coverage; FAIL independent gate | 27 tests, 110 cases, 30 CLI examples pass; reproducible P1 mutants accepted |

## Security and expected missing evidence

Protocol retains approved Python private evaluator, trusted host launcher and Go
agent/MCP split; exact commands/env/mount allowlists; loopback targets; opaque
non-model capabilities and server ACLs; trusted immutable run/schema registration.
Whole-transaction shared run fences, exclusive seal/drain with positive COMMIT
acknowledgment, unknown quarantine/no reset, original snapshot before verifier,
read-only existing-invoice verifier branch, <=2 calls/no retries, second fence and
final unchanged snapshot are explicit. PostgreSQL lock privilege caveat is handled
by inert-column-only UPDATE with no state/token/routing mutation grant. Read-only
and failed-original paths now skip verifier explicitly and preserve positive
agent fence evidence for cleanup. One absolute 30-second post-agent deadline and
<=5-second operations remain separate from the 300-second agent budget.

No additional architecture/security permission expansion observed or performed.
Main evaluation clarification and typed event-example update match these v2
contracts. No documentation or schema test is taken as authentication/DB proof.

**UNRUN; prerequisite BLOCKED as expected:** actual SQL/grants/lock concurrency,
late commit and uncertain COMMIT handling, mount/credential/source isolation,
real artifact byte verification, MCP lifecycle/ACL calls, JSONL capture under
failure, model behavior, real deadlines/resource monitoring and safe reset.
These remain admitted T018–T023/T040 obligations; T001/T007 are not bypassed.
No downstream implementation/runtime task was started. Orchestrator owns status
and integration; source remains frozen and unchanged.
