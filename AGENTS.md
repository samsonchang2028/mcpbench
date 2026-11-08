# MCPBench agent instructions

## Boundaries

- Work only on MCPBench resources. Preserve existing homelab services, containers,
  networks, volumes, GPU drivers, and native Ollama configuration.
- Never use global Docker cleanup, prune, or unscoped Compose teardown commands.
  Keep any future teardown restricted to the verified MCPBench project; preserve
  its volumes unless their deletion is explicitly requested.
- Bind any published MCPBench port to `127.0.0.1`. Use only synthetic billing data;
  real QuickBooks credentials, production data, and invoice sending are out of scope.
- Before image builds, model pulls, inference, or container startup, pass the
  resource and connectivity gate in `docs/IMPLEMENTATION_PLAN.md`. Missing audit
  evidence is an unresolved gate, never evidence of an idle machine.
- Native Ollama configuration changes require review. Do not unload or replace a
  model belonging to another workload. Request settings stay local to our calls.

## Read by task

- Use [task-classifier](agents/task-classifier.md) to choose LIGHT or FULL work.
  Routine, bounded maintenance needs one implementer and a focused check;
  core or sensitive changes retain independent review/testing and explicit gates.
- When coordinating or delegating tasks, use [agents/orchestrator.md](agents/orchestrator.md).
  Assigned workers read [implementer](agents/implementer.md),
  [reviewer](agents/reviewer.md), or [tester](agents/tester.md) instructions for
  their role. Dependencies and readiness live in `docs/TASK_GRAPH.md`; file
  ownership and milestones live in `docs/EXECUTION_PLAN.md`.

- For project scope or current status, read `docs/PROJECT_CONTEXT.md`.
- Before environment operations, read `docs/NODE1_AUDIT.md` and refresh its
  time-sensitive resource, workload, port, and model observations.
- Before implementation, read `docs/ARCHITECTURE.md` and the relevant dependency
  row in `docs/IMPLEMENTATION_PLAN.md`.
- Before tests or benchmark changes, read `docs/EVALUATION_PLAN.md`.

## Implementation and completion

Build the draft-invoice vertical slice first. Only full-context tool exposure is
in scope initially; do not add retrieval engines, embeddings, or vector databases.
Validate tool inputs and compute money on the server, using integer cents.
Use transactions and idempotency for invoice creation; never trust model totals.

Keep deterministic integration checks separate from live model smoke tests.
Record exact dependency and model versions when selected. A check is complete
only with its actual result; label blocked and unrun checks explicitly. Record
material architectural decisions in the existing documents and keep observed
facts separate from proposed settings. Static contract checks are documented in `contracts/README.md`; application
commands remain gated by their DAG tasks.
