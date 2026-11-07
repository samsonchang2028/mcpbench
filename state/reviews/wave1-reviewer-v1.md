# Wave 1 independent review — frozen v1

Verdict: **CHANGES REQUIRED**. Scope: T003, T004 and T005, reviewed independently
against shared assumptions, role rules, TASK_GRAPH and EXECUTION_PLAN. Candidate
identity: `state/candidates/wave1-frozen-v1.json`; local SHA-256 verification
matched all 13 listed files. No candidate source was edited. No runtime, network,
Docker, Git, Ollama, package-install or application operations were performed.

## Findings

### P1 — Settle late writes before the oracle snapshot; order replay explicitly

Areas: `docs/EVALUATION_PLAN.md:73`, lifecycle steps at lines 109–115;
`docs/SECURITY_RESOURCE_CONTRACT.md:59`–63; architecture lifecycle.

Trigger: agent times out/exits while an already-authorized MCP request remains in
flight. Evaluation step 5 immediately snapshots/grades, while security only waits
for writes before reset. A late commit after that snapshot can be omitted from the
oracle's expected/extra-write checks. A transactionally consistent snapshot is not
proof that all task writes have finished. The result can falsely pass or mislabel
an uncertain timeout. Also, required same-key replay has no explicit authorized
position relative to capability revocation.

Smallest fix: define a shared lifecycle with agent stop, bounded initial settlement,
explicit trusted replay checks using the same run/key (and a separately limited
verification capability if needed), final capability revocation plus bounded drain,
then the final immutable snapshot/oracle and scoped cleanup. The exact mechanism
can remain T006 work, but its ordering/invariant must be fixed now. Unknown
settlement must yield comparison-invalid/failed evidence and quarantine, not a
success grade or reuse/reset of potentially active state. Replay costs/timeout
handling must be explicit and identical across strategies. Ensure T003/T004/T005
agree on this lifecycle.

### P2 — Credential wording contradicts fixture exclusion

Area: `docs/SECURITY_RESOURCE_CONTRACT.md:16`.

The opening statement calls records and credentials “fixtures,” while lines 59–60
and the architecture forbid tokens/passwords in fixtures. This can mislead a
future implementer about committing reusable secrets.

Smallest fix: say billing records are fictional fixtures; runtime project-local
secrets belong only to ignored trusted control-plane configuration and never to
fixtures, prompts or logs.

## Acceptance evidence

| Criterion | Result / evidence |
| --- | --- |
| T003: unchanged research question and four strategies | PASS: PROJECT_CONTEXT defines all four and comparable settings, no winner claim |
| T003: Go MCP/agent versus Python evaluator | PASS: architecture/topology and launcher responsibility reconcile the old Go evaluator |
| T003: three-tool smoke then ten executable tools | PASS: exact tools and phased progression retained |
| T003: decisions, assumptions and failures | PASS with P1 repair required for terminal-state lifecycle; model/ports/capacity are honestly unverified |
| T004: task/fixture/event/result prose contracts | PASS as documentation draft: version/identity/field rules, examples, size ceilings and future T006 schema freeze explicit |
| T004: deterministic oracle/reset contract | CHANGES REQUIRED: exact 25,000-cent oracle and scoped fingerprints correct, but terminal snapshot can precede late writes |
| T004: metric definitions and failure attribution | PASS: required create-only set versus relevant three-tool set is coherent; recall 1/1 and precision 3/3 for the given smoke; missing data, failed outcomes and uncertain reasoning attribution preserved |
| T005: principals, server ACLs, trusted routing | PASS: opaque registered run capability, no self-asserted schema/principal, independent per-call ACL checks |
| T005: credential, network and artifact boundaries | PASS subject to P2 wording fix: agent separated from evaluator credentials/expected states, private DB, loopback MCP and honest host-network residual risk |
| T005: resources/deadlines/abort/negative tests | PASS: caps and admission/abort criteria align with shared assumptions; planned tests labeled unrun |
| V1 logging scope | PASS: JSONL/run/call IDs and deterministic artifacts; OpenTelemetry/Jaeger explicitly v2 |
| Documentation-only exception | PASS: explicit blocked-Git exception, exclusive writable lanes and no runtime authority |
| New probe / preregistration ownership | PASS: T040 depends on T007; T008 depends on T040; T039 has exclusive docs/benchmark/PREREGISTRATION.md |
| Cross-document comparison and reproducibility | PASS except P1 lifecycle: fixed permissions/budgets, protected held-out runs and final preregistration remain coherent |

## Missing evidence and deliberate future work

No runtime validation exists or is demanded for these prose changes. T001/T002
host/Git blockers remain real. T006 is not complete: auth/run-mapping protocol,
request/result transport, exact schemas/negative examples, mount/env allowlists and
schema validation must still be frozen and reviewed. T040 and T023 are future,
separately approved live operations; scripted or advertised capability is not live
Qwen success. Application implementation remains blocked.

Re-review the owners' repaired frozen candidate before approval. No open P0 finding;
one open P1 and one P2 on this v1 candidate.
