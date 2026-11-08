# T006 independent review — final repair candidate v3

Verdict: **APPROVE** for the static T006 contract freeze. No remaining P0/P1 finding identified. This approval does not authorize runtime work or bypass T001/T007 and later integration gates.

Reviewed commit `32bafe0607bfb81938d151de6c15e8288e9bc526` in `.worktrees/T006`, including the narrow 11-file diff from reviewed v2 `f18638770218147ff67c90c17df5f2037466efd7`. Candidate identity is frozen by MAIN `state/candidates/T006-v3.json`: all **41 source hashes and 3 main governance hashes match**. Previous reports remain archived separately. Only this main-tree reviewer report was written.

## Prior findings and repair verification

- **Actual unauthorized execution:** the former comparison-valid failed-original counterexample now rejects. A positive actual execution count requires a terminal safety incident, quarantine, invalid comparison and no successful cleanup/reset. Denied attempts remain distinct and can recover. The fix covers original success/failure and invoice/read-only paths without treating ordinary model failures as safety incidents.
- **Host outcome versus original success:** invoice and read-only ControlChain now require a reaped normal zero exit, complete delivery, matching parsed AgentResult with completed status, matching run/attempt, and observed duration within 300000 ms before original PASS. Independently reproduced rejection of timed_out, exit code 2, duration 300001, and each missing/partial/malformed/oversized delivery (with consistent absent parsed result/input). Parsed timeout also rejects original PASS. Known model/tool/retry counts are checked against 8/12/1 for passing outcomes.
- **Observed timing and artifact references:** a known 300001-ms task latency cannot retain agent_budget_pass=true in either workflow. Prior phase result references now match the host-delivered reference by path, byte count and digest, in addition to message identity. Independent mismatched digest rejects. This is explicitly metadata consistency, not proof of external bytes; runtime hash/path verification remains the launcher's obligation.
- **Legitimate failed attempts preserved:** independently validated all six combinations of invoice/read-only with completed-but-wrong, failed and timeout outcomes as comparison-valid failed attempts after known settlement, evidence and cleanup. Independently validated settled timed-out invoice and read-only control chains with original_pass=false and no verifier. No timeout is rescued into success.
- **V1 findings remain resolved:** required typed event payloads and complete/interrupted stream validation; read-only project/timesheet applicability and exact answer/fixture-ID binding; versioned phase/exit/verifier/shared-deadline schemas; coherent assertions/nulls/replay evidence; frozen catalog identity/order; nonretryable authorization/domain/conflict errors. The suite retains the original reviewer and tester regression cases.

## Acceptance mapping

| T006 criterion | Review result |
| --- | --- |
| Ten named bounded tools, smoke3, inputs/results/errors/ACL definitions | PASS static |
| Fixture/task/expected-state and read-only project/timesheet support | PASS static; independent failed-read paths retained |
| Exact draft oracle and annotations | PASS: 25000 cents, two units at 12500, required create only, optional relevant lists |
| Public AgentRequest versus secret/control/oracle boundary | PASS: no oracle/required/relevant hints added to model request |
| Strict parsing, versions, dates, integer money/quantity and canonical hashing | PASS retained; float timing/ratios and missing-metric nulls preserved |
| Offline local schema references and immutable catalog/schema identity | PASS; 313 local registered references |
| Agent/result, manifest, typed JSONL, grading and control/exit/verifier contracts | PASS static with repaired consistency checks |
| Per-call ACL/trusted mapping/fencing/COMMIT acknowledgment/quarantine | PASS normative contract; runtime proof UNRUN |
| No-repair verifier, original/final snapshots and safe scoped cleanup | PASS normative contract; invoice two-call/two-fence gate retained |
| Comparable budgets/four strategies and deferred ranking knobs | PASS retained |
| Approved topology and launch privileges | PASS: no architecture/security expansion |

The established private Python evaluator, host-only launcher, Go host-loopback agent/MCP, separate secret input, narrow mount/env/command/endpoints and read-only grader connection remain intact. Whole-transaction shared fence, exclusive seal/drain with positive COMMIT acknowledgment, the inert-column row-lock privilege caveat and quarantine on uncertainty are preserved. The 300-second task deadline and separate total 30-second post-agent budget, five-second operation bound, two verifier calls/no retries remain unchanged. No retrieval engine, actual SQL grant, image/model operation or OpenTelemetry/Jaeger/dashboard was added. Updated main EVALUATION_PLAN read-only/comparison clarification remains within the previously reviewed design.

## Observed checks

All Python commands used `PYTHONDONTWRITEBYTECODE=1`; only installed local validation dependencies were used.

- `git rev-parse HEAD`: exact v3 commit above.
- SHA-256 verification: **41/41 source, 3/3 governance match**.
- `python3 -m unittest contracts.tests.test_contracts -q`: **32 tests PASS**, including **118 registered cases**, workflow/control/event/incident/budget regressions.
- Direct validation of every manifest-listed standalone example: **30/30 PASS**. This review used direct validation, not an additional subprocess CLI pass.
- Independent reference walk: **313 references**, all local registered definitions.
- Independent negative probes: actual unauthorized comparison; invoice/read-only abnormal host exits and all four bad delivery states; parsed timeout; prior-result digest mismatch; known overbudget task metric: **all reject**.
- Independent positive probes: six legitimate failed-task comparison variants and two settled failed-timeout control chains: **all validate**.

Actual PostgreSQL privileges, concurrency/drain/late commits, COMMIT ambiguity, MCP protocol/server execution, filesystem/process/mount enforcement, reset behavior, live models and resource/performance evidence are **UNRUN**, as required until admitted later tasks. Schemas and static helpers cannot authenticate their record producer or establish real DB/process settlement; the protocol states these limits. This expected absence is not a static-contract failure. No network, DB, Docker, model, install, build, runtime, source edit or subagent operation occurred.
