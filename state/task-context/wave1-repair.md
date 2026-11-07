# Frozen v1 repair instructions

Address independent P1 late-commit/snapshot gap and P2 prose/example wording.
Modify only the original task's reserved files. Do not change state/graph/shared
assumptions. No runtime commands. Coordinate through O, then freeze a new candidate.

## Shared terminal-state lifecycle decision

1. Stop agent execution at result/deadline, preserve its output/events/exit status,
   revoke its execution capability and prevent new agent calls. Do not grade a
   mere process exit as settled state.
2. Boundedly establish that every already-authorized MCP operation has completed
   or rolled back and cannot later commit (actual fence/drain protocol is T006).
   Failure/uncertainty yields `settlement_unknown`, comparison invalid, failed
   smoke gate, retained evidence and quarantined run; do not reuse/reset it while
   writes may still be live. Diagnostic snapshot is not authoritative PASS.
3. Save immutable **agent-only** settled snapshot and grade original DB and answer.
   This is the authoritative task-correctness evidence before any verification
   calls. Replay must never create a missing invoice or repair a failed attempt.
4. Only when original oracle/answer passes, use a separate trusted verifier
   capability (agent never sees it) for bounded same-key/same-payload replay and
   changed-payload conflict check. Constrain it to that settled run/request. Assert
   same invoice ID and no application-state change. Original agent cap stays revoked.
5. Revoke verifier capability, settle/drain again, save final settled snapshot and
   compare with agent-only application state; grade replay/no-extra-write invariants.
   Any late change or unknown settlement fails validation; do not overwrite original
   correctness evidence. The run may have correct task state but failed verification.
6. Persist all evidence, then scoped reset; verify seed fingerprint. Unknown active
   writes mean quarantine, never a risky reset. Capability access is revoked before
   run storage can be reused.

V1 post-agent settlement/verification budget: at most 30 seconds total, at most
5 seconds for each settlement or verification/DB operation, at most two verifier
calls and no verifier retries. This is outside the 300-second agent task deadline
and must be recorded/charged separately in full lifecycle latency/compute, identically
for all strategies. It cannot extend the agent deadline or rescue a timeout.
T006 freezes exact fencing protocol, capability limits and failure schemas.

T003: reflect lifecycle and new bounded verification budget in architecture/context
as appropriate without duplicating entire evaluation contract.
T004: define steps, two snapshots, no-repair replay, settlement_unknown outcome,
original correctness versus verification/run validity, measurement boundaries. Label
task JSON example explicitly a partial projection (or provide all mandatory fields).
T005: align revocation/drain before both snapshots and reset, verifier privilege,
30-second verification bounds/negative test. Say records are fictional fixtures;
secrets live only in ignored trusted configuration, never fixtures/prompts/logs.
