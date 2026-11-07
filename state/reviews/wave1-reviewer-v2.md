# Wave 1 independent review — frozen v2

Verdict: **APPROVE** for documentation tasks T003, T004 and T005. Candidate identity:
`state/candidates/wave1-frozen-v2.json`. All 13 listed source files matched their
SHA-256 values during re-review. This approval covers prose contracts only; it is
not approval for runtime implementation, inference or deployment.

## Findings and resolutions

No open P0/P1 findings and no additional blocking contract inconsistency found.
The archived v1 review's findings are resolved:

- **P1 terminal writes/oracle race:** Agent access is revoked and already-authorized
  operations must settle before the authoritative agent-only snapshot. Unknown
  settlement fails the smoke/comparison-validity gate and quarantines the run;
  diagnostic snapshots cannot PASS and unsafe reset/reuse is prohibited.
- **Replay ordering and no-repair invariant:** Original settled state/answer and
  execution outcome are graded and preserved first. Verification has a separate
  trusted capability constrained to the existing run/request/invoice. It cannot
  create a missing draft, repair a failed task, alter the original verdict or
  rescue a timeout. Verifier access is revoked and drained before the final
  snapshot checks unchanged application state.
- **P2 credential wording:** Billing records are fixtures; runtime secrets now
  explicitly belong only in ignored trusted configuration/runtime delivery,
  never fixtures, prompts or logs.

The repaired lifecycle is consistent in PROJECT_CONTEXT, ARCHITECTURE,
EVALUATION_PLAN, SECURITY_RESOURCE_CONTRACT and shared assumptions. The common
post-agent limit is 30 seconds total, 5 seconds per operation, two verifier calls,
no verifier retries. It includes both fences and snapshot/grading operations,
never extends the 300-second agent deadline, and is recorded separately and
charged to lifecycle costs identically across strategies.

## Acceptance and consistency evidence

| Criterion | Verdict / evidence |
| --- | --- |
| T003: research question and four strategies preserved | PASS: unchanged comparison goals, no assumed winner, comparable principal/model/tasks/budgets |
| T003: Python evaluator and Go server/agent | PASS: private-network evaluator and separate host-network agent; trusted host launcher owns process transport/lifecycle |
| T003: three-tool smoke then ten executable tools | PASS: tool names, phased gates and fictional data scope match graph |
| T003: design choices, assumptions and failure behavior | PASS: host-network residual risk acknowledged; model/ports/capacity unverified; terminal writes/replay lifecycle repaired |
| T004: concrete fixture/task/event/result prose | PASS: version/identity/mandatory-content rules, bounded result transport, JSONL fields, examples, explicit partial-task example and future schema freeze |
| T004: independent oracle and controlled lifecycle | PASS: exact 25,000-cent draft, immutable original snapshot/answer, two settlement fences, no-repair replay, seed fingerprints, quarantined uncertainty |
| T004: retrieval metrics and failure attribution | PASS: create-only required set versus three relevant tools is correct for IDs in prompt; recall 1/1 and precision 3/3; uncertain reasoning and multiple failure stages retained |
| T004: tokens, latency, compute, validity | PASS: all attempts/costs retained, verifier counts separate, null unavailable fields, original correctness distinguished from failed verification/cleanup and invalid comparison |
| T005: principals, permissions and routing | PASS: server ACLs independent of exposure, registered opaque run mapping, trusted verifier distinct from read-only grader/reset credentials |
| T005: credential/network/artifact boundaries | PASS: agent no DB/expected-state/grader/socket access, narrow mounts, loopback publication, private DB and documented host-network residual risk |
| T005: resources, deadlines, abort and negative tests | PASS: proposed caps match shared baseline; 60-second admission and pressure abort rules explicit; planned tests honestly unrun |
| V1 observability | PASS: structured JSONL/run/call IDs and deterministic artifacts; OpenTelemetry, Jaeger and collectors deferred to v2 |
| DAG consistency | PASS: 40 unique IDs, valid prerequisite targets, no self-edges/cycles, 24 topological levels; T040 depends on T007 and gates T008 |
| Exclusive ownership and dispatch exception | PASS: documentation-only T003–T005 exception under blocked Git/runtime; disjoint output files, fixed candidates; T039 explicit docs/benchmark/PREREGISTRATION.md path |
| Approval and role boundary | PASS: no worker marks own task DONE; orchestrator integrates state; runtime remains behind later approval and actual admission evidence |

Observed structural check used Python standard-library SHA-256 verification and
parsed task dependency rows/topological traversal. Semantic review compared the
frozen candidate documents and role rules against the shared assumptions and
user kickoff. No application test is claimed or required for these prose changes.

## Remaining freeze and runtime blockers

T006 is **not complete**: machine-readable schemas/negative examples, exact auth,
capability/run-mapping provision/revoke/fence protocol, request/result transport,
launch/env/mount allowlists and validation evidence remain future work. The prose
now fixes necessary behavior while explicitly leaving those implementation-level
formats to that node. Its eventual contract examples must encode both settlement
fences, non-repair replay and the shared bounds.

T001/T002 host/Git restrictions remain unresolved. Installed model identity,
loading, tool support, Docker workloads and ports are not verified by this review.
T040 and T023 remain future separately authorized runtime operations. No runtime,
network, Docker, Git, Ollama, dependency install or source-edit operation was
performed by this reviewer. Only this report was written.
