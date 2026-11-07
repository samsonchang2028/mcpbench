# Access refresh independent documentation test

Overall gate: **PASS** for T002 normal Git evidence and T003–T005 documentation
refresh candidates. No open P0/P1 documentation inconsistency found.

Candidate manifest: `state/candidates/access-refresh-v1.json`.

| Task | Frozen commit | Observed gate |
| --- | --- | --- |
| T003 | 45256c86b7c06d8ef2cf7fd950aa7a0e991816bb | PASS |
| T004 | fdc6f6209b9b5e0a0456296b6c83589eb5ab82b1 | PASS |
| T005 | 49db92c9008bf0192f6830ce336c01c7830da566 | PASS |

## Actual checks and methods

Ran local standard-library Python assertions through the shell, using pathlib,
json, re, hashlib, os.access and read-only subprocess Git commands. Only this
report was written; no source, tests, worktrees or other state files changed.

- SHA-256 of all 14 frozen main governance/evidence files and all four candidate
  documentation files matched the manifest.
- For each worktree, `git rev-parse HEAD` matched the frozen commit and
  `git status --porcelain` was empty. `git diff 0116054..HEAD --name-only` matched
  exactly the allowed source paths; `git diff 0116054..HEAD --check` passed.
- Candidate relative write paths were disjoint. Main source hashes remaining
  unchanged also confirm no edits to the frozen main governance surface.
- T002: main `git rev-parse --show-toplevel` equals this MCPBench path;
  `git cat-file -t e0ce746...` is commit; `git show -s --format=%P e0ce746...`
  has no parent (normal initial commit); `.git` is writable by the current user.
  `git remote` is empty. `git check-ignore -q` passes for `.env`, artifacts,
  .aws, .codex, .agents and orchestrator-managed .worktrees paths. The initial
  commit and task commits are actual successful write evidence; the tester did
  not perform another write probe or change Git configuration.
- Parsed the authoritative DAG table: 40 unique IDs, all T001–T040 present, valid
  dependencies/priorities/statuses, no self edges or cycles, 24 topological levels.
  Every active candidate has complete prerequisites. Current frozen states are
  T001 BLOCKED; T002/T003/T004/T005 CANDIDATE; T006/T007/T008/T040 WAITING.
  T040 depends on T007 and T008 depends on T040. Integration may change states
  only after independent approval/testing, never treat CANDIDATE as DONE.
- Checked 50 local Markdown links and five fenced blocks across frozen main
  Markdown and actual worktree candidate documents: targets exist, fences balance.
- Both evaluation JSON examples parse and declare schema_version 1. The task
  example is explicitly a partial projection, not a valid complete task fixture.
  Required tool is create-draft; all three smoke tools are relevant. These match
  the documented 1/1 recall and 3/3 precision for full context.
- Removing only T004's new readiness-evidence section makes its complete document
  byte-for-byte equal to the prep-commit evaluation contract.
- Exact section comparisons against prep commit preserved architecture trust
  boundaries, terminal lifecycle and billing/catalog contract, plus security
  principal matrix, ACL/routing and terminal lifecycle sections.
- Curated resource/model/Docker JSON evidence parses. Resource sample retains
  30 two-second intervals over 60.02 seconds, zero consecutive swap intervals.
  Model metadata records qwen3.5:9b, Q4_K_M, advertised tools and an empty loaded
  model list. Candidate documents report these as observations, not live proof.

One tester assertion initially searched case-sensitively for lowercase “partial”
while the document correctly says “Partial task projection.” The assertion was
corrected to accept case-equivalent wording; no source change was needed. The
complete rerun above passed.

## Semantic acceptance traces

| Criterion | Result and evidence |
| --- | --- |
| T002 safe normal repository access | PASS: actual baseline and task commits, writable metadata, correct root and ignore rules; no remote/push |
| T003 current architecture/context | PASS: restored Git/Docker/Ollama access distinguished from remaining service-account storage restriction; exact tag/digest/quantization observed; Python evaluator and Go server/agent unchanged |
| T004 evaluation-first contracts | PASS: complete previous contract unchanged outside new evidence section; independent oracle, scoped reset, errors, null metrics and equal budgets preserved |
| T005 security/resource boundary | PASS: restored Codex access does not transfer to benchmark agent; no protected-directory/Docker/sudo workaround; host-network residual risk retained |
| Terminal write settlement | PASS: revoke/drain before original immutable snapshot, no-repair verifier replay only after original task pass, second revocation/drain and final unchanged-state snapshot before reset |
| Unknown settlement | PASS: invalid comparison and quarantined state, no unsafe reset/reuse; original correctness never overwritten |
| Verification budget | PASS: same separate 30-second total, 5-second operations, two verifier calls/no retries, costs included without extending 300-second agent deadline |
| Product fidelity | PASS: same research question/four strategies; three-tool smoke then ten executable baseline; JSONL/run IDs/artifacts v1, OpenTelemetry/Jaeger v2 |
| Metadata versus live capability | PASS: advertised tools/empty ps are not T040/T023 success or future exclusive access; context metadata does not expand request budget |
| Resource and service baseline | PASS: sampled headroom not full T007, parent disk not actual protected model target; unhealthy Immich ML/GPU mismatch are existing constraints, not repaired or blamed on MCPBench |

No new P0/P1 defect found. Some governance sections retain explicitly superseded
historical statuses; the latest refresh section and authoritative DAG consistently
show current candidate/waiting states. O should update current-state prose during
final status integration rather than reuse historical blocked-Git wording.

## Deliberate blockers and unrun checks

- T001 remains BLOCKED pending an authorized service-account verification of the
  actual model-store target/symlink/filesystem/free space. This is a real Unix
  boundary, not a documentation failure and not permission to work around it.
- T006 machine-readable schemas/authentication/fencing contracts are unfinished.
  T007 full admission and T040/T023 observed live behavior remain unrun/unapproved.
- The installed GPU runtime mismatch and existing unhealthy Immich ML container
  remain recorded. No host repair is part of this test gate.
- No runtime, application, Docker, network, Ollama or package commands were run.
  No application tests exist or are needed for this prose-only refresh. Numeric
  audit evidence was checked from the supplied frozen artifacts, not remeasured.

This PASS authorizes documentation integration only; it does not authorize builds,
startup, generation, model loading, configuration changes or public exposure.

UTC report: 2026-11-07T23:02:11.261590+00:00
