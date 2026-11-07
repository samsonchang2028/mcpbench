# Independent review — access-refresh frozen v1

Verdict: **APPROVE** for T002 Git evidence and the T003–T005 documentation refresh.
No open P0/P1 review finding. This approval covers documentation/Git readiness,
not T001 completion, full admission, live model behavior or application execution.

## Candidate identity and scope

Reviewed `state/candidates/access-refresh-v1.json`, including all 14 main-file
hashes and four task-document hashes. Every source hash matched. Task candidates:

| Task | Frozen commit | Exclusive changed paths |
| --- | --- | --- |
| T003 | `45256c86b7c06d8ef2cf7fd950aa7a0e991816bb` | docs/PROJECT_CONTEXT.md, docs/ARCHITECTURE.md |
| T004 | `fdc6f6209b9b5e0a0456296b6c83589eb5ab82b1` | docs/EVALUATION_PLAN.md |
| T005 | `49db92c9008bf0192f6830ce336c01c7830da566` | docs/SECURITY_RESOURCE_CONTRACT.md |

All three worktrees were clean, HEAD matched the manifest, and each diff from
preparation commit `0116054764a4506151820df73225b7869433d74d` changed exactly its
reserved files. Main governance files were reviewed separately; old main copies
of the four task documents were not mistaken for the proposed candidates.

## Acceptance review

| Criterion | Verdict and evidence |
| --- | --- |
| T002: normal repository access and own-project scope | PASS. `git rev-parse --show-toplevel` resolves /home/sfkim/projects/mcpbench; root commit is `e0ce746b1e91bbed5afc6e950ff2d516ff7c8883`; baseline tree contains only MCPBench root documentation, agents/, docs/ and state/. Task commits provide additional normal index/object/ref write evidence. No remote is configured. |
| T002: safe write/ignore rules | PASS. Recorded temporary project-local write/fsync/delete and normal initialization are not permission bypasses. Local `git check-ignore` confirms .env, artifacts/, .worktrees/, .aws/, .codex/ and .agents/ examples are excluded. Current main changes are expected orchestration metadata, not an unrelated repository or application change. |
| T003: architecture and product fidelity | PASS. Python evaluator, Go MCP server/agent, trusted launcher, private DB, three-tool smoke then ten tools, four unchanged strategies and comparable budgets remain intact. Host facts are separated from proposed deployment. |
| T004: evaluation contract preservation | PASS. Diff adds a bounded readiness section without changing oracle, lifecycle, metrics, schema examples or protected split/preregistration contracts. Required creation versus relevant optional listing tools remains coherent. |
| T005: security/resource contract preservation | PASS. Newly available control-plane access does not grant runtime-agent privilege. Ordinary service-account model-directory denial is preserved; no Docker/privileged mount workaround is permitted. Numeric sampling is not a substitute for complete admission. |
| Prior terminal-write P1 remains fixed | PASS. Agent revoke/settle before immutable original oracle, non-repair replay under separate verifier authority, verifier revoke/drain before final snapshot/reset, uncertain-settlement quarantine and the common 30-second verification limits are unchanged. |
| V1 observability and later scope | PASS. Structured JSONL/run IDs/deterministic artifacts remain v1. OpenTelemetry, Jaeger and collectors remain v2; no retrieval implementation or runtime code was introduced. |
| Model evidence and availability | PASS as documentation of observed metadata. Curated API evidence agrees on qwen3.5:9b/Q4_K_M, server 0.40.13, exact digest and empty loaded-model snapshot. No document claims that advertised tool support passes T040 or that an idle snapshot reserves future exclusive use. |
| Host evidence and residual risks | PASS. The 60.02-second retained sample has 30 two-second intervals, no sustained swap and 90–94% idle CPU. The actual protected model target/filesystem remains unverified; parent free space is not presented as proof. GPU mismatch and pre-existing unhealthy Immich ML are recorded baseline conditions, not repaired or hidden. |
| DAG/dependencies/ownership | PASS. 40 unique task IDs, valid targets, no self edges/cycles, 24 topological levels. Current CANDIDATE roots have no unfinished prerequisites; T006 waits for their review. T040 depends on T007 and gates T008. T039's exclusive preregistration path is retained. |

## Check methods

Read-only local checks executed against the manifest and fixed worktrees:

- SHA-256 comparison of every main/task source listed in the manifest.
- `git rev-parse`, `git log`, `git remote`, `git status`, `git check-ignore`, root
  tree inspection, worktree `git diff <prep>..HEAD --name-only` and `--check`.
- Full scoped candidate diffs against the preparation commit, semantic comparison
  with prior accepted contracts and curated audit JSON.
- Standard-library DAG parsing/topological validation, exclusive-path assertions,
  Markdown local-link existence and balanced-fence checks for the task candidates.

No source/worktree/state file was changed except this review report. No host,
Docker, network, Ollama, package-install or application command was run by this
reviewer. Live claims were assessed only against the existing audit artifacts;
they were not independently re-executed.

## Integration and remaining gates

O may accept T002 and integrate the three reviewed task commits after the separate
tester gate passes. Recalculate DAG/state metadata afterward: T003–T005 return to
DONE and T006 becomes READY, not DONE or automatically dispatched. Keep current
status prose synchronized when accepting T002; candidate wording that it awaits
validation is accurate at this review instant, not a permanent readiness statement.

T001 remains BLOCKED on actual model-store target/filesystem verification by an
authorized service-account check. T006 machine schemas/auth/run mapping/fencing
protocol, T007 complete fresh admission and T040 real tool probe remain incomplete.
No application task is genuinely READY under the present dependency graph. The
next safe wave is contract freezing plus resolving the remaining audit evidence;
runtime implementation and live execution still require their stated approval and
gates. Existing host issues are operational limitations, not P0/P1 defects in this
documentation refresh.
