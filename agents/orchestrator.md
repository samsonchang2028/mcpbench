# Orchestrator

Coordinate MCPBench tasks, ownership, review, testing and integration. Use the
`mlb-agent-workflow` and `token-efficient-coding` skills when available, applying
MCPBench's rules rather than MLB-specific domain requirements.

## Read first

Read [AGENTS.md](../AGENTS.md), [TASK_GRAPH.md](../docs/TASK_GRAPH.md) and
[EXECUTION_PLAN.md](../docs/EXECUTION_PLAN.md). Read `state/CURRENT.md` and the
assigned task/context pack if present; do not assume those files exist.
The user's kickoff is the product authority; reconcile older architecture through
T003. The graph owns dependencies/status; the execution plan owns file lanes.

## Dispatch and integration

First apply [task-classifier](task-classifier.md). Classify obvious cases inline;
spawn a classifier only when useful. LIGHT work uses one implementer (which may
be the orchestrator), explicit allowed files, and a focused check. It needs no
separate reviewer/tester, new context pack, reservation record or worktree when
the current checkout has exclusive ownership. Update existing task/state records
only when applicable. Report the actual check result. Escalate to FULL if scope
grows or impact becomes uncertain. Explicit task acceptance gates still apply.

The following full workflow applies to FULL tasks:

1. Select a READY task whose prerequisites are DONE. Check unresolved contracts,
   external blockers and required resource gates; document work can proceed when
   runtime work is blocked. Do not treat a task's priority as permission to start.
2. Prepare `state/task-context/<ID>.md`: task ID, acceptance criteria, read-first
   paths, stable contracts, allowed/forbidden write paths, validation commands,
   runtime gates and expected handoff. Create state records only when needed.
3. Reserve exclusive paths in `state/agents/<ID>.md`, recording owner, lifecycle,
   candidate revision/content hash, branch/worktree if available, activity,
   validation results and blockers. Own all graph/state/shared-manifest edits.
4. Once Git works, provision a task branch/worktree within writable roots.
   While Git is blocked, follow the execution plan's restriction on coding-agent
   dispatch. Never bypass protected metadata. Workers do not manage worktrees,
   merge or push main independently.
5. Dispatch the [implementer](implementer.md). Parallel tasks need complete
   dependencies, stable shared contracts and disjoint write surfaces. Serialize
   shared dependencies, manifests and integration changes.
6. Freeze a candidate, then assign the [reviewer](reviewer.md) and
   [tester](tester.md). They may work concurrently on that same candidate if the
   author pauses edits and the tester has a separate reserved test surface.
   Changed code invalidates previous evidence for affected behavior.
7. Return findings and failed tests to the implementer. Recheck the repaired
   candidate. For repeated failures, record the unresolved cause; resolve routine
   issues autonomously and ask the user only for missing decisions or access.
8. Integrate only when every acceptance criterion has evidence, R has no open
   P0/P1, V reports PASS for required checks, and any lower-priority deferrals are
   recorded. Update task status and `state/CURRENT.md`, release reservations,
   then enable dependent nodes. No Git integration is claimed while Git is blocked.

## Host safety and completion

Keep one resource lease for costly Node 1 operations, regardless of worktree count.
Admission and stop rules live in [IMPLEMENTATION_PLAN.md](../docs/IMPLEMENTATION_PLAN.md).
Recheck them before builds, downloads, model pulls, startup or inference. Missing
host evidence blocks those actions; host access never transfers to the benchmark
agent. Preserve native Ollama and existing services/volumes.

Handoff: completed task IDs, candidate identity, changed paths, reviewer verdict,
tester evidence, unresolved risks, newly READY tasks and externally blocked tasks.
Role files define procedures; they do not start workers or services automatically.
