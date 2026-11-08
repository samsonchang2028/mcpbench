# Independent T006 tester

Read AGENTS.md, agents/tester.md, state/task-context/T006.md and accepted
ARCHITECTURE/EVALUATION_PLAN/SECURITY_RESOURCE_CONTRACT docs. Candidate will be
provided as a frozen commit in .worktrees/T006. Source ownership contracts/** only.
Exclusive output report in main: state/reviews/T006-tester.md. No source edits.

User goal authorizes automatic routine transitions but no runtime gate bypass.
T001 remains genuinely blocked on private model directory/sudo; validate contracts
using installed Python/jsonschema only. No network, package installs, Docker, DB,
model calls or builds. Local read-only Git and Python validation/test commands okay.

Require complete, implementable v1 contracts: ten named tools and smoke3 subset;
input/output/errors, authorization, IDs/bounds, catalog; fixtures/expected state;
request/result/public-vs-secret envelope; run manifests; typed JSONL events and
grading/metrics; concrete control-plane run mapping/receipt/fence protocol. Ensure
unknown fields, duplicate keys, NaN/Infinity, schema version, dates, argument money/
quantity and cross-field inconsistencies reject. Canonical hash deterministic;
explicit wire integer policy consistent with parser, preserved missing-metric nulls,
float ratios/durations allowed where declared; no silently fetched schema refs.
Valid/invalid examples for every major object and all tools, plus meaningful tests.
Preserve exact 25000-cent oracle and required create-only vs optional relevant lists.
Existing documentation example compatibility must be resolved explicitly.

Security: opaque per-run capability outside model request/logs, server ACLs and
immutable registered schema mapping; no arbitrary SQL/path/URL from caller. Every
operation holds run fence for whole transaction. Exclusive seal must acknowledge
COMMIT after drain before original snapshot; unknown => quarantine/no reset/PASS.
Replay only after original state/answer/outcome success; separate verifier cannot
create absent invoice, <=2 calls/no retries. Final seal/drain precedes final snapshot
and safe scoped reset. Post-agent total30sec incl snapshot/grading, per-op5sec,
not extending300sec task. Verify PostgreSQL lock privilege caveat is handled without
granting state/capability/routing mutation to MCP role. SQL/DB proofs explicitly
unrun until admitted T018. Protocol diagrams alone must not claim runtime proof.

Keep Python evaluator/private DB versus Go agent/host loopback/Go MCP service,
trusted host launcher only, narrow artifacts/mount/env/command allowlists. No actual
credential examples or privileged/socket mounts. This is within approved architecture;
identify any actual expansion/security-sensitive change needing user approval.
All four strategy identifiers and comparable budgets remain, ranking knobs T026.
OpenTelemetry/Jaeger/dashboard excluded from v1.

Report exact candidate identity, acceptance mapping, observed commands/results,
P0/P1 findings and missing evidence. Runtime UNRUN is expected, not a static-task
failure. Reviewer APPROVE/CHANGES REQUIRED/BLOCKED; tester PASS/FAIL/BLOCKED.
