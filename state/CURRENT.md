# Current state

UTC update: 2026-11-07T22:48:40.695224+00:00

DONE: T003 architecture/context, T004 evaluation contracts, T005 security/resources.
Independent v2 reviewer APPROVE and tester PASS; no open P0/P1 documentation finding.
Candidates: state/candidates/wave1-frozen-v2.json and matching snapshots.
Reports: state/reviews/wave1-reviewer-v2.md and wave1-tester-v2.md.
Handoffs: state/handoffs/T003.md, T004.md, T005.md; write reservations released.

READY but not dispatched/approved: T006 machine-readable contract freeze.
BLOCKED: T001 host audit/access; T002 writable Git metadata/normal initialization.
WAITING: all other tasks, including resource gate T007 and early probe T040.
No application code, package install, Docker operation, inference, service change,
Git commit/merge, or restriction bypass occurred. Next wave needs user approval.

V1 uses Python evaluator + Go MCP server/agent, JSONL/run IDs/deterministic artifacts.
OpenTelemetry/Jaeger v2. T040 depends T007 and additionally gates T008; T039
exclusively owns docs/benchmark/PREREGISTRATION.md (future, not created).

T006 must freeze schemas, launcher/env/mount limits, trusted auth/run mapping and
write-settlement/fencing proof, including post-agent verifier capability rules.
Unknown write settlement invalidates/quarantines without unsafe reset/reuse.
