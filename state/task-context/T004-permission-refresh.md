# T004: permission-refresh documentation assignment

Read AGENTS.md and agents/implementer.md; current docs/NODE1_AUDIT.md,
docs/WAVE1_CONTRACT_ASSUMPTIONS.md, TASK_GRAPH row and EXECUTION_PLAN latest
permission-refresh section. Reuse curated state/audits data, no new host checks.

Worktree: /home/sfkim/projects/mcpbench/.worktrees/T004
Allowed source paths relative to this worktree: docs/EVALUATION_PLAN.md
All commands/edits must use that worktree, never the main checkout or another
worker's files. Do not change state/graph/assumptions/manifests.

Goal/acceptance: Verify and minimally update evaluation documentation for newly reachable host metadata and verified installed model; keep metadata capability vs live T040 distinction, exact oracle, reset/settlement/no-repair replay, JSONL schemas/metrics/budgets, T006 future. Do not rewrite accepted contracts gratuitously. Add concise current readiness/evidence statement linking latest audit; numeric sample is not T007 completion.

Scope: approved documentation refresh. Dependencies: none. Earlier accepted docs
are historical evidence, not permission for runtime work. T001 remains BLOCKED on
actual model directory target/filesystem. Git baseline e0ce746 normal, not a bypass.
T002 awaits independent validation; no remote/push. T006 schemas not dispatched.

No network, Docker commands, Ollama requests, model loads, builds, dependencies,
application code or host service changes. Local source/link checks only.
After editing, git diff --check; stage/commit ONLY the assigned doc paths on your
assigned task branch (allowed task-local Git writes); no branch/worktree lifecycle,
merge, cherry-pick or push. Return commit ID, paths, decisions, checks and remaining
blockers, then pause edits for independent review/testing. No subagents.
