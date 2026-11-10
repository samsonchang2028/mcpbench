# T019 settlement Python review

Current candidate: `127e06a0814c191982171be759b1efb69384c92d` in
`.worktrees/T019`. Verdict: **APPROVE**, scoped to the Python settlement changes
and focused quota correction; no open P0/P1 findings in this scope.

Original candidate: `3c18d276476c78c0f514ac8c51d4a3d7bb6adc74`, compared with
`5c3dd4a` (settlement lane originally `170a67e`). Original verdict:
**CHANGES REQUIRED**, for the P1 retained below and now resolved.

Scope: only `db/lifecycle.py`, `db/tests/test_lifecycle.py`,
`eval/runner/lifecycle.py`, `eval/runner/test_lifecycle.py`,
`launcher/run.py`, and `launcher/test_run.py`. Focused re-review adds
`eval/runner/artifacts.py` and `eval/runner/test_artifacts.py`, and examines only
the four-file delta `3c18d27..127e06a`; earlier timing/failure-path conclusions
remain applicable. Adjacent transport and contract code was read only to
establish caller behavior and invariants.
Independent Go review and verification are separate gates. No tests, runtime,
SQL, Docker, model calls, or private credential reads were performed.

## Original P1 — quota exhaustion loses the evaluator exit journal (RESOLVED)

Location: `launcher/run.py:141–143`, interacting with the existing
`eval/runner/artifacts.py:82–84`; regression at `launcher/test_run.py:175–176`.

Trigger: evaluator execution produces enough retained output to exceed the
aggregate 100 MiB cap, or leaves less free capacity than the exit/result journal
requires. `DockerTransport.execute()` can return an actual uncertain/timed-out
Outcome after its quota callback rejects the run. `request()` correctly builds
the corresponding ProcessExit, but `self.host` is an `Artifacts(self.root)`:
its write checks the size of the entire run tree before publishing. Consequently
the exit write itself raises `ArtifactError('artifact_limit')`; a fully validated,
bound result can also fail its following journal write after the exit consumes
the last available capacity. The existing entered marker still prevents reuse,
but the actual ProcessExit and/or valid exact result bytes are absent from the
journal, violating the explicitly required quota-failure evidence behavior.

The new quota matrix replaces only `Launcher.quota` with a throwing lambda;
it leaves `Artifacts.size()` below its real cap, so it cannot detect this case.

Smallest useful correction: guarantee bounded room for exit/result evidence
within the unchanged aggregate cap before admitting evaluator output, and use
that room for the failure journal. Do not solve this by increasing the cap or
discarding prior evidence. Add a focused regression that exercises the actual
artifact writer's capacity check (a smaller injected cap is sufficient),
requires the actual typed exit plus complete valid bound result bytes when
present, and requires quarantine/no progression/no reset/no reuse.

## Other scoped conclusions

- Receipt and evaluator event elapsed values now use nonnegative integer ceil;
  this preserves the integer canonical/hash contract and conservatively charges
  fractional durations. Existing backend/evaluator deadline checks remain.
- Event canonicalization and durable publication precede both event-list
  mutations. The injected publication failure test checks quarantine, no
  snapshot capture, an uncontaminated persisted state, and no further reset.
- Positive submillisecond regression cases exercise receipt canonicalization
  independently and evaluator event/phase-state/snapshot publication separately,
  addressing both diagnosed floating-point producers.
- For outcomes that leave journal capacity available, the launcher independently
  classifies delivery, retains actual ProcessExit before exit/delivery/deadline
  rejection, copies exact validated result bytes before those rejections, and
  appends only accepted outcomes to the successful chain. The new matrix covers
  exit 1, missing/malformed/identity/budget failures, signal, timeout, unreaped,
  spawn failure, expiration, and per-operation overrun; blocked prepare is covered.
- No frozen schemas, canonical serializer, fixtures, budgets, reset rules, or
  quarantine/reuse safeguards are changed by these six files. Root's observed
  old-run `agent_sealed` generation 1 with revoked capabilities is registry
  evidence only, not original positive ACK proof or authorization to reset.

## Focused resolution review — `127e06a`

- Before each evaluator admission, the host creates exactly two finite,
  phase-specific slots: 64 KiB for ProcessExit and 1 MiB for exact result bytes.
  Ordinary `write_bytes` physically writes and charges these allocations under
  the existing aggregate cap. Allocation failure prevents child admission.
- Slot consumption is limited to fixed evaluator phase paths and validates
  typed evidence. Result publication rechecks identity/phase/message correlation,
  exact result-ref hash/length/path, and equality with the already persisted exit.
  It retains the supplied original bytes without reserialization. No arbitrary
  caller path or outside-run storage is introduced.
- Slots use the existing no-follow directory traversal, require regular private
  owner files with one link and their original capacity, fsync the rewritten
  file, publish with a non-replacing hard link, and fsync the containing directory.
  Completed evidence cannot be replaced or consumed a second time. Only reserved
  whitespace allocation is reclaimed; retained payloads are preserved.
- The launcher checks real aggregate quota immediately after execution and
  records failure before either slot shrinks. It publishes exit and available
  valid result first, then rejects a recorded quota failure even when consuming
  slots has brought the run back below the cap. This prevents an over-cap success
  from advancing to verifier/reset or producing a successful ControlChain.
- New launcher cases use a smaller actual cap and fill the real run tree to
  near/over capacity; they require the ordinary artifact writer to reject an
  unreserved write. They cover nonzero exits, apparent success after overshoot,
  expiration, and injected result-publication failure; assert exact retained
  bytes, unchanged retained payload size, quarantine, no successful chain,
  no verifier, no further reset/cleanup, and the restart prohibition. Helper tests
  additionally cover typed/binding rejection and second-publication rejection.
- The 100 MiB production cap, integer canonical serializer, frozen schemas,
  budgets, and existing unknown-ACK/quarantine safeguards remain unchanged.

Checks: static source/contract review completed on the exact candidates above.
Execution evidence: **UNRUN by this reviewer**, as assigned. Root separately
reported **96 focused tests PASS in 13.869 seconds**; this is supplied evidence,
not an execution result produced by this reviewer. Build/live runtime remain
separate root-owned gates. Approval does not authorize old-run reset or reuse.
