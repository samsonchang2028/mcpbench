# T019 runtime repairs — independent tester

## Retest: frozen 127e06a0

Exact candidate `127e06a0814c191982171be759b1efb69384c92d`, same T019 worktree,
2026-11-09. **Required offline repair checks: PASS.** Source-gate closure still
requires the independent reviewer's P1 recheck; full T019 live acceptance remains
UNRUN by this tester. Historical 3c18d276 results and its quota P1 are preserved
below rather than retroactively relabeled.

The exact delta from 3c18d276 changes only eval/runner/artifacts.py,
eval/runner/test_artifacts.py, launcher/run.py and launcher/test_run.py. HEAD was
verified before and after testing; worktree status remained empty. No runtime,
Docker, SQL, model, install or credential operations were performed.

Actual command from `.worktrees/T019`:

```sh
env PYTHONDONTWRITEBYTECODE=1 /home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python -m unittest db.tests.test_lifecycle eval.runner.test_artifacts eval.runner.test_lifecycle launcher.test_run launcher.test_transport
```

PASS, **96 tests in 13.789s**, exit 0. Session `81315`, final chunk `807361`.
Expected negative CLI diagnostic remains visible. This includes actual
Artifacts.size/write rejection, finite precharged slot consumption, launcher
near_exit1/over_exit1/over_success/near_expired/result_failure scenarios, prior
failure matrix, fractional timing, durable event state, and transport guards.
The candidate's capacity test uses a reduced 2MiB cap to exercise real accounting;
it does not mock quota failure. The independent checks below additionally use the
actual unchanged production 100MiB cap.

Independent stdin harness, same pinned interpreter/environment, no source or
test-file writes: **2 tests PASS in 0.895s**, exit 0. Session `60261`, final
chunk `61b8e2`. Explicit suite loading selected only the independent TestCase.
Reproduction specification and actual assertions:

- `IndependentQuotaChecks.test_real_100MiB_capacity`: instantiate the existing
  LauncherTests fixture separately for each of near_exit1, sticky_over_success,
  near_expired and result_publication_failure. Wrap its real scripted transport
  after evaluator settle-grade returns. Assert Launcher.LIMIT and host.max_bytes
  both equal `100*1024**2`; never patch either. Create one synthetic mode0600
  sparse retained-independent-payload.json of `LIMIT-host.size()-1` bytes, or
  `LIMIT-host.size()+1` for sticky_over_success. Assert actual aggregate size is
  exactly cap-1/cap+1. A real host.write of unreserved evidence must raise
  artifact_limit. near_exit1 uses the backend's actual unknown-agent/quarantine
  result and exit1; near_expired advances its clock31sec; publication failure
  injects only publish_control_result failure after the actual capacity check.
  All four run_attempt calls raise quarantined. Load/validate the actual
  ProcessExit: complete delivery, exit1 for near_exit1, exit0 for the other three.
  Complete journal result bytes equal evaluator result bytes, except the
  injected publication failure, where the result is absent and its reserved slot
  remains. After slot consumption aggregate size is below100MiB in all cases;
  the earlier over-cap success nevertheless cannot progress. The retained
  payload's exact original size is unchanged; host.max_bytes remains100MiB.
  Quarantine exists, no successful ControlChain or verifier invocation exists,
  reset count is exactly one initial prepare reset, no cleanup occurs and restart
  fails FileExistsError. Fixture cleanup runs only after assertions.
- `IndependentQuotaChecks.test_result_binding_rejections_do_not_consume_slot`:
  reserve real prepare slots, construct valid typed ProcessExit/ControlResult
  from frozen examples with exact raw SHA256/length/ref, and publish exit. Try
  separately altered result run_id, phase and message_id and altered exit
  result_ref path, SHA256 and byte count. Every attempt raises ValueError and
  leaves artifact size unchanged. Publishing the original pair then succeeds
  and exact result bytes match. Thus rejected evidence cannot consume the slot.

The independent actual-cap checks inspect file sizes and retained journal bytes;
the large filler is sparse synthetic data. They do not delete/truncate filler to
make publication succeed. Candidate source likewise consumes only precharged
finite slots; no root cap increase or payload-removal escape was introduced.
Result-publication failure retains the previously published exit and quarantines;
it does not falsely claim durable result delivery to the journal.

```sh
git diff --exit-code 3c18d276..127e06a0 -- contracts eval/fixtures go.mod go.sum internal tests/integration observability
git rev-parse HEAD
git status --short
```

PASS, empty diff/status, exact full candidate output; chunk `01bafc`.
No Go sources/dependencies, contract/fixture files, or observability sources changed,
so the prior complete Go suite and unaffected Python/Compose results remain
applicable to unchanged content. No redundant Go repeat was performed.

The original real-quota evidence gap is now covered by actual-cap independent
execution, including sticky failure after an overshoot has been reduced by slot
consumption. These results supply offline tester evidence for the reserve repair;
they do not replace source review or fresh admitted live acceptance.

## Original candidate: 3c18d276

Candidate: `3c18d276476c78c0f514ac8c51d4a3d7bb6adc74`, compared with
`5c3dd4a`; tested in `/home/sfkim/projects/mcpbench/.worktrees/T019` on
2026-11-09. **Executed offline checks: PASS; source gate remains unresolved.**
Independent review reports an open P1 actual-quota evidence-retention defect;
the passing mocked-quota matrix does not cover it. Actual full-stack T019
acceptance remains **UNRUN by this tester**.

Read MAIN's latest T019 context pack and both context/settlement diagnosis reports,
AGENTS, classifier/tester/orchestrator instructions and evaluation plan. This is
FULL work. Candidate source stayed unchanged; the only persistent tester write
is this MAIN report. Python is the cached T008 virtualenv, Python 3.14.4;
Go is go1.26.8 linux/amd64. No installs, image builds, Docker daemon mutations,
SQL connections, native model calls/config changes, or credential-file reads.
Docker Compose was used only for sanitized static configuration rendering.

## Actual commands and results

All commands below ran from the candidate worktree. Shell tool sessions/chunks
are evidence handles from this tester turn, not runtime artifact identifiers.

```sh
env MCPBENCH_TEST_PYTHON=/home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python GOMAXPROCS=1 GOTOOLCHAIN=local GOPROXY=off go test -mod=readonly -p=1 -count=1 ./...
```

PASS, exit 0; session `14866`, final chunk `6d870d`. All packages passed:
cmd/agent, internal/{agent,billing,gateway,mcp,ollama,store}, observability,
tests/integration and tests/integration/scripted-agent. cmd/billing-mcp and
cmd/mcp-gateway reported no test files. Integration-package success here is
offline evidence and does not establish actual PostgreSQL acceptance.

```sh
env PYTHONDONTWRITEBYTECODE=1 /home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python -m unittest contracts.tests.test_contracts eval.fixtures.test_fixtures db.tests.test_lifecycle eval.runner.test_artifacts eval.runner.test_lifecycle launcher.test_run launcher.test_transport containers.test_check_config eval.grading.test_oracle eval.reset.test_contract observability.test_jsonl db.tests.test_offline
```

PASS, **190 tests in 18.015s**, exit 0; session `78560`, final chunk `498945`.
The expected CLI-negative diagnostic `mcpbench: expected fixed evaluator phase`
appeared during the passing suite.

```sh
env PYTHONDONTWRITEBYTECODE=1 /home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python containers/check_config.py
```

PASS, exit 0, chunk `61a1db`: six identities/limits, internal MCP/DB, loopback
gateway, separate narrow agent/verifier mounts and pinned bases. The checker
renders with `--env-file /dev/null` and an environment containing PATH only;
it does not contact the daemon, build, or start containers.

```sh
env MCPBENCH_TEST_PYTHON=/home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python GOMAXPROCS=1 GOTOOLCHAIN=local GOPROXY=off go test -mod=readonly -p=1 -count=1 -v ./internal/agent ./tests/integration/scripted-agent -run 'TestFullContextCompleteBusinessHistory|TestToolErrorContentKeepsEnvelope|TestFailedTerminalResultsArePublished|TestScriptedModelReadsCompleteBusinessContent|TestScriptedCLICompleteHistoryAndOverflow'
```

PASS, exit 0; session `36583`, final chunk `5603e2`; internal/agent 1.140s,
scripted-agent 0.341s. An earlier invocation of the same command yielded partial
output without retaining its session handle; the fully observed repeat above
is the authoritative focused result.

```sh
git diff --exit-code 5c3dd4a..3c18d276 -- contracts eval/fixtures
git rev-parse HEAD
git status --short
```

PASS: contract and fixture files have no changes from baseline; HEAD is the
exact full candidate above; worktree status is empty. Chunk `f03b11`.

## Criterion evidence

| Criterion | Result | Actual evidence |
| --- | --- | --- |
| Captured complete context reaches final turn | PASS | Actual Runner with full captured-size schemas/history completes 4 model calls / 3 tool calls / 0 retries and exact invoice ID `INV-1FE3C5398ABE8BC078918EEF8DF44A72`; actual scripted CLI parser also completes. |
| Existing guard and exact boundary retained | PASS | Serialized fourth request is 3564 bytes plus 512 output allowance = 4076. Adding 20 bytes is admitted at 4096; adding 21 fails before fourth model call with failed 3/3/0 and retained context_overflow. |
| All business fields and tool correlation retained | PASS | Replay compares complete business Result content, assistant selections, ToolName/ToolCallID and full schemas; event/internal envelopes retain is_error=false and 25000-cent total. Error-envelope test also passes. |
| Failed terminal child result is durable | PASS | Scripted run and verify return unsuccessful execution after publishing validated failed AgentResult/VerifierResult, closed connection and valid failure events; verifier retains 1 call/0 retries. Setup failure does not invent a result. Overflow CLI preserves failed 3/3 result. |
| Positive fractional receipt time canonicalizes | PASS | Backend test advances 0.25ms, requires integer elapsed_ms=1, validates FenceReceipt and canonical_bytes. Existing deadline/unknown-commit/reset safety tests pass. |
| Positive fractional event time/state persist | PASS | Microsecond-advancing evaluator clock reaches verify, publishes canonical integer event timing, private settle-grade state, agent snapshot and JSONL. |
| Durable event publication precedes state append | PASS | Injected event write failure produces quarantine, no published event and empty state events; no snapshot, extra reset or cleanup. Source ordering matches the assertion. |
| Failed evaluator outcomes preserve true exit and available validated result | PASS for executed cases; actual quota gap open | Existing 12-scenario matrix covers quarantine, missing, malformed, identity/budget mismatch, signal, timeout, unreaped/spawn failure, expired/overdue and mocked quota. Blocked prepare exit 1 retains typed result. No verifier/progression, success chain or unsafe reset. Real artifact exhaustion is not proven by that mock. |
| Additional independent journal boundaries | PASS | Four extra adversarial subcases described below pass; valid result bytes survive exit 1 and a later transport-write failure, signal -9 is preserved as null exit code plus SIGKILL, wrong phase is malformed delivery. |
| Frozen contracts, fixtures and deployment scopes | PASS | Baseline diff empty for contracts/fixtures; static Compose render and contract tests pass. |

## Independent supplemental harness

Ran a Python stdin unittest harness using the same pinned interpreter and
`PYTHONDONTWRITEBYTECODE=1`; no file or candidate edit was used. Session `21327`,
final chunk `8710eb`: **11 tests PASS in 5.504s**. This includes the imported ten
LauncherTests plus one independent test with four subcases.

Reproduction recipe: for each subcase instantiate `launcher.test_run.LauncherTests`,
call setUp, wrap its ScriptedTransport.execute and run its normal run_attempt.
At evaluator settle-grade, after normal fixture execution:

1. `wrong_phase`: replace result.phase with finalize and write canonical bytes.
2. `valid_result_exit_one`: return `Outcome(1, True, 'exited', None, observed.ended_monotonic)` with the valid result unchanged.
3. `result_transport_write_failure`: wrap Launcher.fixed_transport to raise
   `OSError('synthetic_transport_write_failure')` when name is result.json after
   settle-grade has executed; leave actual result and exit unchanged.
4. `negative_signal_exit`: return `Outcome(-9, True, 'terminated', 'SIGKILL', observed.ended_monotonic)` with valid result unchanged.

All subcases assert run_attempt raises quarantined; load and validate the actual
journal/settle-grade-exit.json as ProcessExit. Wrong phase must have malformed
delivery, all others complete; exit code must be respectively 0, 1, 0 and null,
with SIGKILL in the last case. For complete deliveries compare journal result
bytes exactly with evaluator/control/settle-grade-result.json. Assert quarantine
exists, no control-chain exists, reset count remains one (initial prepare only),
no cleaned backend call and no verifier invocation. Always call fixture.doCleanups.

No supplemental source tests were added or changed. Existing candidate tests were
inspected and executed independently rather than treating implementer results as
proof. Full Go/Python coverage additionally exercises billing oracle negatives,
reset guards, event validation and artifact bounds.

## Open review defect and remaining gates

Root relayed the independent reviewer P1 after these checks completed; see
`state/reviews/T019-settlement-reviewer.md`. Real aggregate exhaustion can make
Artifacts.size reject journal writes before the launcher's later quota check,
losing the evaluator ProcessExit/result. The existing quota scenario replaces
Launcher.quota with a throwing lambda while real artifact usage stays below the
cap. My additional result-transport failure injection also does not establish
actual quota retention. **This candidate must not pass the source gate.**
Author is preparing a bounded finite journal reserve under the unchanged 100MiB
aggregate cap. Independent testing of actual near-cap/over-cap usage on the new
frozen candidate remains UNRUN; no repair implementation is tested by this report.

UNRUN here: actual repaired images and launcher against real owned PostgreSQL,
official MCP plus scripted model, independent exact 25000-cent persisted-state
grading, actual fences/replay/unchanged-state proof, concurrent duplicate and
timeout-after-commit runtime checks, reset fingerprint and complete runtime trace.
These require root's fresh admission and explicit runtime ownership. Native Qwen
support/inference is also UNRUN and cannot be inferred from scripted results.
Existing quarantined runs remain authoritative and must not be reset or reused.
Offline PASS does not mark T019 DONE or supply live acceptance evidence.
