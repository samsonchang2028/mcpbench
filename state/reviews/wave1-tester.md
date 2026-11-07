# Independent documentation test — wave 1, frozen v2

Overall gate: **PASS for documentation acceptance**. No open P0/P1 test findings.
The v1 grading/quiescence P1 and both reported P2s are resolved. This verdict does
not assert application, host, Docker or Ollama readiness. T006 remains incomplete.

## Candidate identity and unchanged-source check

Manifest: `state/candidates/wave1-frozen-v2.json`; snapshot directory uses the same
stem. All 13 source SHA-256 values and snapshot bytes matched; hashes were checked
again immediately before saving this report. Authors remained paused.

- `docs/PROJECT_CONTEXT.md`: `4df52bccf1d3e072a8199276657a3716c9677ff3ec448fe13f88d0378770e887`
- `docs/ARCHITECTURE.md`: `942ae8a5dfaec759a45f61d088808d2b2d4fafffeb1c30fa8a9e9c8f07790a25`
- `docs/EVALUATION_PLAN.md`: `e219f6b1cf57779626cfe56a585ce31d77c7a35846c6948ee1dcb43848048c12`
- `docs/SECURITY_RESOURCE_CONTRACT.md`: `692774b633dfd618601e59a96cf460a17f96bbfb31ba506e2a4a8fca90d8d4f2`

## Commands and observed checks

Read-only commands included `cat state/task-context/wave1-tester.md`,
`cat state/candidates/wave1-frozen-v2.json`, `cat docs/EVALUATION_PLAN.md`,
`rg -n -C 5 'fenc|quiesc|replay|settle|freeze|probe|T007'` over the candidate
architecture/security/context/graph/shared-assumption documents, and targeted
`sed -n` excerpts for lifecycle, budgets and principal boundaries.

Two `python3 - <<'PY'` standard-library checks used `pathlib`, `hashlib`, `json`
and `re`; no test files were added. They performed these assertions:

| Check method | Actual result |
| --- | --- |
| SHA-256 each manifest source and compare bytes with frozen-v2 snapshots | PASS: 13 files |
| Resolve relative Markdown links; triple-fence counts modulo 2 | PASS: 43 local links and balanced fences in all 13 files |
| Parse task table: exactly T001–T040, six columns, valid priorities/statuses, existing parents/no self edge, complete prerequisites for active nodes | PASS: 40 tasks |
| Repeatedly remove dependency-free nodes | PASS: no cycle; 24 topological levels |
| T040 parents exactly T007; T008 includes T040; T039 names exclusive preregistration path; T007 distinguishes early/basic T040 versus end-to-end T023 | PASS |
| Resolve all task references in frozen files | PASS |
| Set intersection of T003/T004/T005 surfaces; verify allowed paths appear in respective context packs | PASS: exclusive ownership, four candidate implementation documents |
| Parse two fenced JSON examples; check complete event mandatory fields, schema version, source enum and integer sequence | PASS |
| Check task excerpt declares itself partial and not a valid complete task | PASS; future schema-required fields remain mandatory |
| Check required/relevant tool lists and invoice arithmetic | PASS: only create-draft required, all three smoke tools relevant; 2 × 12,500 = 25,000 cents; precision 3/3, recall 1/1 |
| Check equivalent settlement/quarantine/deadline/call-count/retry vocabulary across architecture, evaluation, security and shared assumptions | PASS after correcting an overly literal tester assertion, explained below |
| Final source-manifest hash recheck before report write | PASS |

The first vocabulary assertion required the exact enum `settlement_unknown` in
shared assumptions, which use equivalent “unknown settlement” prose. That assertion
failed for test-method specificity, not a candidate defect. A corrected check
normalizes whitespace/Markdown and accepts the explicit enum or equivalent prose,
then checks quarantine, 30 seconds total, 5 seconds per operation, two verifier
calls, no retries and the separate agent-deadline invariant. All four documents
passed without any source change. No check failure remains unexplained.

## Criterion-level acceptance evidence

| Criterion | Verdict / evidence |
| --- | --- |
| T003 architecture and product reconciliation | PASS: Go server/agent, Python evaluator, controlled host launcher, three-tool smoke → ten executable tools, private DB and fixed loopback endpoints |
| T003 research fidelity | PASS: full context, semantic top-k, authorization/metadata+keyword+vector hybrid and hierarchical domain retrieval retained; no presumed winner |
| T003 meaningful tradeoffs/failures | PASS: host-network residual risk explicit; source access errors do not imply absent services; budgets/proposals distinguish measured facts |
| T004 fixture/task/event/result contracts | PASS for prose stage: concrete required fields, exact invoice oracle, versioning/invalid-output behavior, partial example clearly labeled; full machine schemas remain T006 |
| T004 independent grading and reset | PASS: immutable original settled snapshot, read-only oracle, unchanged rows/idempotency record, reset fingerprint, failures retained before cleanup |
| T004 metrics/failure attribution | PASS: required versus relevant tools distinct; null missing metrics, stage/call evidence, uncertain attribution, failed attempts and comparison validity reported; verifier costs separate and included in lifecycle totals |
| T005 principals/auth/routing | PASS: server per-call ACLs, opaque trusted run mapping, separate evaluator/grader/verifier capabilities; agent has no DB/reset/expected-state privileges |
| T005 resource/negative-test policy | PASS: same proposed admission/caps/deadlines, explicit stop and quarantine rules, scoped-only faults/cleanup; native Ollama and homelab services preserved |
| V1 observability | PASS: JSONL/run IDs/call IDs/deterministic artifacts; OTel/Jaeger/collectors deferred to v2 |
| Approval and ownership boundaries | PASS: docs-only exception, private writes, future runtime approval/admission for T040, no completed T006/runtime claim |
| T006 machine schemas, exact fence/auth transport and implementation | UNRUN / not completed: outside this approved wave |
| Runtime/model/container/application behavior | UNRUN: intentionally unauthorized/access-blocked and not required for documentation PASS |

## Manual adversarial lifecycle traces

1. **Normal invoice:** agent result → stop/revoke new agent calls → establish all
   accepted operations terminal → original settled snapshot/oracle/answer verdict
   → issue separate run/request-constrained verifier capability only after original
   success → at most same-key replay and changed-payload conflict → revoke/drain
   verifier → final settled snapshot equal to original application state → save
   all evidence → scoped reset/fingerprint. PASS across T003/T004/T005.
2. **Late commit after client timeout:** process exit alone never authorizes an
   oracle verdict. Drain must establish terminal completion/rollback before the
   authoritative original snapshot. Agent timeout remains failure; verifier
   activity cannot extend the 300-second agent budget or rescue it. PASS.
3. **Unknown in-flight state:** bounded settlement failure produces
   `settlement_unknown`, null authoritative oracle where unestablished, invalid
   comparison/failed smoke gate, diagnostic evidence and quarantine; no unsafe
   reset/reuse. PASS.
4. **Missing/wrong original invoice:** original failure remains immutable; verifier
   cannot create the invoice or repair state. No replay occurs before original
   DB/answer success. PASS.
5. **Late verifier mutation:** second fence/drain precedes final snapshot; unexpected
   application-state change fails verification without replacing original evidence.
   Unknown verifier settlement quarantines without reset. PASS.
6. **Verification budget exhaustion:** identical 30-second total post-agent bound,
   5 seconds per settlement/verifier/DB operation, at most two verifier calls and
   no verifier retries apply to all strategies. Costs are recorded separately and
   included in lifecycle compute/latency; no extension of agent budget. PASS.

No new cross-document P0/P1 inconsistency was found. Exact implementation of the
fence/drain, run-capability provisioning, launch allowlists and full JSON schemas
is intentionally assigned to T006 and must be validated before code/runtime work.

## Ownership and runtime limits

Only `state/reviews/wave1-tester.md` was written. No candidate, task status or
manifest was changed by the tester; no source tests were added. No network,
application, Git, Docker, Ollama, dependency-install or service operation ran.
The orchestrator owns final task status/integration and future-wave dispatch.
