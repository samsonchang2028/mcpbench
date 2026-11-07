# T005: permission-refresh documentation assignment

Read AGENTS.md and agents/implementer.md; current docs/NODE1_AUDIT.md,
docs/WAVE1_CONTRACT_ASSUMPTIONS.md, TASK_GRAPH row and EXECUTION_PLAN latest
permission-refresh section. Reuse curated state/audits data, no new host checks.

Worktree: /home/sfkim/projects/mcpbench/.worktrees/T005
Allowed source paths relative to this worktree: docs/SECURITY_RESOURCE_CONTRACT.md
All commands/edits must use that worktree, never the main checkout or another
worker's files. Do not change state/graph/assumptions/manifests.

Goal/acceptance: Refresh security/resources documentation to distinguish restored Codex access from ordinary Unix model-store denial, actual GPU mismatch, baseline unhealthy Immich ML, and numerical resource sample vs full admission. Keep strong boundary: do not use docker/privilege workaround to read protected service files. No actual runtime verification. Preserve reviewed permissions/lifecycle/budgets and JSONL v1.

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
