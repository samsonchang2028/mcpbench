# Wave 1 independent reviewer

Read AGENTS.md, agents/reviewer.md, docs/WAVE1_CONTRACT_ASSUMPTIONS.md,
docs/TASK_GRAPH.md and docs/EXECUTION_PLAN.md. Read frozen candidate manifest
state/candidates/wave1-frozen-v2.json once present and its listed files.

All implementation authors are paused. Do not edit any candidate source.
Exclusive output: state/reviews/wave1-reviewer.md. No runtime, Git, Docker,
network, Ollama, package-install or application operations. No subagents.

T003 acceptance: architecture/context reconciled to kickoff; Go MCP server and
agent, Python evaluator, three-tool smoke then ten executable tools; same four
strategies; residual assumptions/failures explained. T004: concrete fixture/task/
event/result contracts, reset/independent oracle, metrics, failure attribution,
missing data, honest results. T005: principal matrix, strict process/credential/
run isolation, resources, deadlines, stop rules and measurable negative tests.
V1 JSONL/run IDs/deterministic artifacts only; OTel and Jaeger v2. Native Ollama
unchanged. Shared topology: host launcher sequences private-network evaluator
prepare → host-network Go agent → private evaluator grade/reset. Agent no DB
credentials/expected oracle data/socket/listener. Final schemas are T006 future.

Check T040's T007 dependency, T008 depends on T040, T039 exclusive output,
documentation-only dispatch exception, state path references and cross-doc
consistency. Exact model, host inventory, ports and Git remain unverified/blocked.
Do not demand runtime tests for documentation or mark T006 complete. Identify
any prose contracts that cannot be implemented without guessing behavior.

Write observed evidence and criterion-by-criterion verdicts to your report.

Report APPROVE/CHANGES REQUIRED/BLOCKED; include concrete P0/P1 findings and smallest fixes, task/area, and cross-document contract conflicts. Treat lower-level inconsistencies according to actual impact; do not invent measured capability.

Revalidation target v2: verify all v1 findings corrected, including terminal-write
settlement before immutable original oracle, gated no-repair verifier replay,
verifier revoke/drain/final snapshot, unknown-state quarantine, common separate
30s post-agent bound, 5s/operation, two verifier calls/no retries. Task example
is explicitly partial; T007 distinguishes T040 from T023; credentials wording
excludes fixture storage. Review semantic cross-document consistency anew.
