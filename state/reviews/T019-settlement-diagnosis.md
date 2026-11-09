# T019 settlement diagnosis — frozen 5c3dd4a

Read-only source diagnosis of `run-e19ac6733790474c4062544d`, 2026-11-09.
No production edits, SQL, Docker, network, model calls, installs or secret-file
reads were performed by this worker. Only this report and ignored
`artifacts/diagnostics/t019-settlement/` were written. FULL-sensitive diagnosis;
implementation and independent review/testing remain with the orchestrator.

**Finding: the frozen evaluator cannot persist real floating-point settlement
timings through its integer-only canonical artifact serializer.** Two independent
producer paths reproduce the observed failure after a successful synthetic seal.
This is concrete evidence of an artifact serialization defect, not evidence that
the PostgreSQL fence transaction failed.

Observed retained evidence:

- `evaluator/agent/exit.json`: reaped, exited 1, result delivery missing,
  duration 1745 ms. Its exact retained ArtifactRef and identity pass
  `Evaluator.child('agent')` offline. Missing result is an admitted failed-agent
  path; synthetic execution of this path still seals and captures successfully.
- `evaluator/control/settle-grade-result.json`: valid failed/quarantine result,
  `settlement_unknown`, no receipt, 1410 ms elapsed / 28590 ms remaining.
  Thus the retained budget observation is not a 30-second exhaustion.
- `evaluator/evidence/settle-grade-quarantine-evaluation.json`: failed agent,
  task latency 1745 ms, no settlement verdict. `evaluation()` obtains this
  latency from `self.state['exit']`, which `settle_grade()` sets immediately
  after loading the child and immediately before sealing. The evaluator reached
  that boundary; failure is not inferred solely from the absent AgentResult.
- There is no published `events/evaluator-1.jsonl`, agent-only snapshot or
  `private/settle-grade-state.json` (filenames/stat only for private state).
  `control/evaluator-settle-grade.stderr` says the evaluator phase failed.
- Root's independently admitted read-only registry diagnostic,
  `artifacts/admission/t019/gateway-smoke-01-registry-diagnostic.json`, observes
  `agent_sealed`, generation 1, lock marker 0, agent token revoked and verifier
  token absent. This observes registry state; it does not retroactively provide
  the original positive ACK receipt, prove a smoke PASS or authorize reset.

The exact artifact failure chain is:

1. `db/lifecycle.py:388–392` returns a schema-valid FenceReceipt with
   `elapsed_ms=max(0, (self._clock()-started)*1000)`. A positive real duration
   is a Python float, even if its numeric value happens to be integral.
2. `eval/runner/lifecycle.py:136` independently computes event `elapsed_ms` as
   a float for a positive monotonic delta. FenceReceipt/Event schemas admit
   these numbers, and their semantic validators pass.
3. `Evaluator.event()` validates, then appends the event to both event lists
   **before** trying to persist it. At line 142, `canonical_bytes(row)` rejects
   any float recursively (`contracts/validate.py:136`,
   `floating number in canonical hash input`). Either the nested receipt timing
   or the top-level event timing is independently sufficient.
4. The broad `invoke()` catch converts this to `settlement_unknown`. It writes
   quarantine and the evaluation summary, whose budget values are integers.
   It then writes the valid ControlResult at `result()` line 202.
5. `result()` subsequently writes private phase state at line 205. That state
   still contains the appended event with the float, so the same serialization
   exception escapes to the CLI. The result file exists, no phase-state file
   exists, and CLI prints the generic error and returns 1. This matches the
   retained failure pattern without a failing SQL operation.

Existing constant-zero test clocks hide this: `max(0, 0.0)` returns the integer
first argument; the scripted receipt also uses an integer fixture timing.
T018's backend-only success can coexist with this failure: validating an
in-memory receipt does not exercise evaluator event/state publication.

**Separate confirmed launcher defect:** `launcher/run.py:110` raises for any
nonzero evaluator exit before loading an already-published phase result and
before writing the typed ProcessExit at lines 128–134. The evaluator CLI
deliberately returns 1 for quarantine/blocked actions even on ordinary handling.
The offline launcher repro generates such a result, then confirms that both
`journal/settle-grade-exit.json` and `journal/settle-grade-result.json` are absent.
The actual journal likewise retains only generic `launcher_incomplete`, hiding
the observed exit and the existing typed result from the transport journal.

Smallest proposed corrections, requiring source-owner changes and review:

- Keep the integer-only canonical/hash contract. Emit integer milliseconds at
  the two timing producers: ceil nonnegative backend receipt elapsed time, and
  ceil nonnegative evaluator event delta before adding the existing integer
  source offset. Do not floor durations in a way that hides deadline excess;
  retain all existing deadline checks and the 5000/30000 ms bounds. Rounding the
  receipt alone leaves the independent event-timing defect.
- Serialize and durably publish each event before appending it to persisted
  in-memory state. This avoids contaminating fallback state when event
  publication fails. It does not turn artifact failure into success or permit
  reset. Preserve sanitized failure evidence; do not log raw driver exceptions.
- Journal the evaluator's actual typed ProcessExit before rejecting a nonzero,
  signaled, timed-out or unreaped outcome. Classify delivery independently from
  exit success: an existing complete, validated, identity/phase/budget-bound
  ControlResult can be retained with `exit_code=1`; missing/malformed outcomes
  retain the true exit with null result correlation. Preserve immutable bytes
  and refs before raising. Avoid a new early exception during result parsing,
  quota or expired-budget handling that again skips the exit journal.
- Nonzero/unreaped/invalid outcomes still stop progression and quarantine, with
  no verifier, retry, reset or reuse. Do not weaken the successful ControlChain
  requirement at `contracts/validate.py:643` that evaluator exits be 0. A failed
  attempt's standalone ProcessExit/result evidence must survive even when a
  complete successful chain cannot be emitted. No schema change is necessary.

Focused offline evidence command (cached Python, frozen source):

```sh
PYTHONDONTWRITEBYTECODE=1 .worktrees/T008/.venv/bin/python artifacts/diagnostics/t019-settlement/repro.py
```

Actual final result: **4 tests PASS in 0.474 seconds**, including two independent
float-source subcases. Output is retained in
`artifacts/diagnostics/t019-settlement/results.txt`. Tests assert the current
defects as diagnostic observations; they are not acceptance proof of a fix.
The initial synthetic missing-result harness omitted its fixture task identity;
that harness-only mistake was corrected before the final focused run.

Required fix regression coverage: use positive submillisecond monotonic deltas
and a real-shaped receipt; require durable fence event + phase state + snapshot
instead of quarantine from serialization. Cover receipt and event timing
independently; exercise `canonical_bytes` round-trip of their retained state.
Inject event write failure and require safe fallback without contaminating state
or resetting. For launcher, cover valid quarantine/blocked result with exit 1,
missing/malformed result with exit 1, signal, timeout, unreaped process and
identity/budget rejection; every observable outcome must retain its actual
ProcessExit and must not advance. Run the existing evaluator/launcher suites
after those changes. Independent corrected-source R/V and any new admitted live
run remain **UNRUN** here. The original schema/quarantine must remain preserved.
