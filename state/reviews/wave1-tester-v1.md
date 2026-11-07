# Independent documentation test — wave 1, frozen v1

Overall gate: **FAIL — P1 grading/quiescence contract gap**. Structural checks PASS.
No runtime, application, Docker, Git, network or Ollama commands were executed.
Only this report was written. No test files or candidate sources were changed.

## Candidate identity

Tested `state/candidates/wave1-frozen-v1.json` and matching snapshot directory.
All 13 manifest SHA-256 values matched their live source files and snapshots.

- T003 context: `101bbd4b8be8c251b33bf402353de8bfe8ca9ab14f6a52974ab11a0029e14b03`
- T003 architecture: `e9613e80aece29c02845137e322d57d0127b43706fc24e92b61ed9e9bdf8f451`
- T004 evaluation: `fddfcf3c728d3f7d87552d00d5bea1175e2b36a72b84d7b7e3a846d329606fb2`
- T005 security: `20e2b4f572bc17a9d0f9af22a50281a4c753b6a4b41c7182a2da95b62442b51f`

## Observed checks

Read commands: `cat state/task-context/wave1-tester.md`, `cat agents/tester.md`,
`cat AGENTS.md`, `cat docs/WAVE1_CONTRACT_ASSUMPTIONS.md`,
`cat docs/TASK_GRAPH.md`, `cat docs/EXECUTION_PLAN.md`,
`cat docs/EVALUATION_PLAN.md`, `cat docs/SECURITY_RESOURCE_CONTRACT.md`,
`cat docs/IMPLEMENTATION_PLAN.md`, and the other role files. Targeted lifecycle
inspection used `nl -ba docs/EVALUATION_PLAN.md | sed -n '31,140p'`,
`nl -ba docs/ARCHITECTURE.md | sed -n '78,101p'`, and
`nl -ba docs/SECURITY_RESOURCE_CONTRACT.md | sed -n '55,78p'`.

One read-only `python3 - <<'PY'` standard-library program used `pathlib`, `hashlib`,
`json` and `re`, with assertions for the following observed results:

| Check method | Result |
| --- | --- |
| SHA-256 each manifest path; compare source bytes with frozen snapshot bytes | PASS: 13 files |
| Parse local Markdown links and resolve relative to source parent; count triple fences modulo 2 | PASS: 43 local links, 13 files with balanced fences |
| Parse six-column task rows; unique IDs exactly T001–T040; existing dependency targets/no self edges; validate priorities/status; active tasks have DONE prerequisites | PASS: 40 tasks |
| Repeatedly remove nodes with no remaining dependency parents | PASS: no cycle; 24 topological levels |
| Assert T040 parents exactly [T007], T008 includes T040, T039 criterion names docs/benchmark/PREREGISTRATION.md | PASS |
| Resolve every Tnnn reference in all 13 frozen files against node map | PASS |
| Set-intersect T003/T004/T005 exclusive file lists and check each lane's context pack lists its own paths | PASS: four implementation documents, no overlapping writes |
| Parse both fenced JSON examples with json.loads; assert event mandatory keys/source enum/integer sequence/schema_version | PASS: 2 parseable examples; event matches declared mandatory fields |
| Assert task required_tool_ids is create-draft only; relevant_tool_ids contains create plus customer/item listing | PASS |
| Arithmetic and denominator sanity | PASS: 2 × 12,500 = 25,000 cents; full-context precision 3/3 and minimal required recall 1/1 |

These are documentation checks, not machine-schema validation or executable
behavior tests. T006 schemas do not exist yet and remain required future work.

## Acceptance mapping and semantic findings

| Criterion | Verdict / evidence |
| --- | --- |
| T003: Python evaluator, Go agent/MCP, separate control plane, 3-tool smoke → 10 executable tools | PASS: context/architecture agree with shared assumptions |
| T003: four unchanged retrieval strategies, no winner assumption | PASS: all four definitions and equal permission/model/budget rule retained |
| T003: meaningful topology/resource/failure tradeoffs | PASS with P1 lifecycle gap below: private DB, loopback APIs, host-network residual risk and unverified capacity documented |
| T004: fixture/task/event/result prose contracts and independent exact invoice oracle | PASS with P2 example clarity below: field/invariant tables and 25,000-cent DB/answer/idempotency assertions present |
| T004: controlled reset, grading, failure attribution and deterministic evidence | FAIL P1: snapshot barrier does not require settled in-flight writes before grading |
| T004: metrics and required versus relevant tools | PASS: IDs in prompt make only create required; optional lists do not inflate recall denominator; token/compute missingness, stage attribution, failures and denominators explicit |
| T005: principals/credentials/ACLs/trusted run routing | PASS: direct server enforcement, run-scoped capability, separate read-only grader/reset roles, no agent DB/admin credentials |
| T005: timeout/cancellation/reset safety | FAIL P1 when read with T004: in-flight write barrier is required only before reset, not the grading snapshot |
| T005: resources/admission/abort/negative tests | PASS: budgets agree across shared assumptions, architecture and evaluation; meaningful negative expectations; actual host checks remain unrun |
| V1 JSONL/run IDs/artifacts; OpenTelemetry and Jaeger v2 | PASS throughout candidate source and current T017 |
| T039 ownership and T040 separate admission/approval | PASS; T040 does not replace T023 end-to-end invoice proof |
| T006 completeness | UNRUN / not complete: machine schemas, exact auth/run mapping and transport freeze intentionally outside this wave |
| Host capability, model tool calling, Docker/network/security runtime behavior | UNRUN: intentionally unauthorized and access-blocked; not a reason by itself to fail this documentation gate |

### P1 — grading can race a late MCP commit

`docs/EVALUATION_PLAN.md:73` permits the grader snapshot after agent exit or
termination; lifecycle step 5 at line 112 immediately snapshots/grades following
execution. `docs/ARCHITECTURE.md:85` similarly snapshots after execution.
`docs/SECURITY_RESOURCE_CONTRACT.md:61–63` requires revocation and no in-flight
MCP writes only before reset/reassignment. None requires the same barrier before
the snapshot used as correctness evidence.

Reproduction by contract trace: a tool request is accepted; the client times out
and the agent exits; the evaluator snapshots no invoice and grades failure; the
server commits afterward; cleanup later waits for quiescence and resets. The
saved oracle evidence no longer represents settled attempt state. A consistent
PostgreSQL snapshot alone does not establish application quiescence.

Small fix: require a trusted admission/revocation fence plus verified settlement
or cancellation of in-flight run writes before the grading snapshot and before
reset. If the barrier cannot be established inside its bounded control-plane
policy, preserve evidence, classify state/oracle as uncertain, mark comparison
invalid and quarantine the run. Add the late-commit adversarial expected test
and reconcile architecture, evaluation and security lifecycle text.

### P2 — task example is incomplete relative to its required-field table

`docs/EVALUATION_PLAN.md:41` requires permitted tools, expected state, final-answer
rule and budgets. Its task example at lines 51–62 lacks those fields. The example
parses and correctly illustrates relevance; it is not a complete future valid task.
Label it explicitly as a partial excerpt that must not pass full T006 validation,
or add the required content. This does not change the required-tool annotation.

### P2 — T007 still says live tool behavior belongs only to T023

The T007 row's final sentence predates T040. The new task correctly establishes an
earlier observed tool-call probe, while T023 proves the real invoice. Update that
sentence to distinguish basic T040 behavior from T023 end-to-end correctness.

## Gate boundary

Report is FAIL pending P1 repair and independent recheck of a newly frozen
candidate. No claim of application, environment or model verification is made.
The orchestrator owns candidate repair assignments, task statuses and integration.
