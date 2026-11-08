# MCPBench project context

Current execution: the user authorized autonomous routine DAG transitions. T006
contracts are implemented and independently approved; T009 fixtures are independently approved.
Go/MCP/DB/model runtime gates remain pending T001/T007/T040 and later task evidence.
Older documentation-wave status below records that stage, not a continuing
per-wave approval requirement. See state/CURRENT.md and TASK_GRAPH for live status.

## Goal and scope

Research question: how do MCP tool retrieval strategies affect agent task success,
latency, token usage, cost and reliability as tool catalogs scale? MCPBench is an
independent systems engineering benchmark using fictional billing/ERP records.

Compare four strategies without assuming a winner: full context supplies all
authorized schemas; semantic top-k ranks task/schema embeddings; hybrid combines
authorization/metadata filtering, keyword search and vector similarity;
hierarchical retrieval selects domains before individual tools. Use comparable
model configurations, principals, tasks, starting state and total budgets.

V1 first proves a three-tool draft-invoice smoke slice, then a ten-executable-tool
baseline with customers, items, projects, timesheets and invoices. Larger catalogs
and other retrieval implementations follow the DAG's baseline/fairness gates.

## Agreed architecture

- **Go MCP server:** simulated billing tools, server-side authorization, validation,
  integer-cent arithmetic, transactional draft writes and idempotency.
- **Small Go agent:** MCP discovery/tool execution and native Ollama chat; no DB,
  evaluator credentials, expected-state fixtures, shell tool or Docker socket.
- **Python evaluator:** fixture preparation/reset, independent database-state oracle,
  failure classification, structured artifacts and summaries. It runs on the private
  benchmark DB network, separately from the agent's runtime principal.
- **Trusted host launcher:** sequences evaluator prepare → agent execute → evaluator
  grade/reset. It handles process transport and container lifecycle under trusted
  control-plane policy; no model can invoke it or choose its arguments.
- **PostgreSQL and dedicated Compose resources:** seeded fictional records, isolated
  per-run state, project-owned volumes and no DB host publication. Keep existing
  native Ollama; do not deploy a second inference server.
- **V1 observability:** structured JSONL with run/call IDs, versioned manifests,
  snapshots and deterministic evaluation artifacts. OpenTelemetry and Jaeger are
  deferred to v2 and are not baseline dependencies.

See [architecture](ARCHITECTURE.md) for topology, trust boundaries and tradeoffs.
MCPBench deployment names, bindings and budgets remain proposals pending admission;
the audit's existing-host observations are time-stamped evidence, not reservations.

## Current status — 2026-11-07

This remains a documentation scaffold, with no application or Compose
implementation. The user authorized a parallel T003/T004/T005 documentation refresh
after changing permissions. Each task uses an isolated Git worktree and exclusive
files; the orchestrator owns independent review/testing and task integration.
No dependency installation, model pull, build, startup or inference is included.

The refreshed [audit](NODE1_AUDIT.md) verifies normal Git, Docker daemon and native
Ollama metadata access. Git was initialized normally on `main`, with baseline
commit `e0ce746`; no remote or push was configured. The earlier read-only metadata
projection was not bypassed. T002 awaits independent validation of that evidence.

The host is a Dell Precision 5520 with i7-7820HQ and Quadro M1200 PCI device.
About 25 GiB RAM and 229 GiB on the project/Docker/parent-model filesystem were
available at inspection; a retained 60-second sample showed zero swap activity
and 90–94% idle CPU. Docker inventory found 15 running and four exited containers,
including Immich and Jellyfin. `immich_machine_learning` was already unhealthy.
NVIDIA reports a loaded-driver/NVML-library version mismatch; GPU offload is not
established. Preserve these existing services and drivers without repair.

Ollama client/server version 0.40.13 exposes installed `qwen3.5:9b`, Q4_K_M,
digest `56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90`.
Tools are advertised in metadata, while `/api/ps` reported no loaded models at
inspection. Neither observation proves live tool-calling or future exclusive use.
Loopback 11434 is verified; candidate 18081 had no listener but must be rechecked.

T001 remains narrowly BLOCKED on the actual Ollama model-storage path/symlink
target and its filesystem/free space. The service-account directory cannot be
traversed by the current user; parent-directory space is insufficient evidence.
Do not alter permissions or use a privilege workaround. T006 schemas, full T007
resource/connectivity admission and T040 live capability verification remain
incomplete. The numeric resource sample does not waive any of these gates.

The shared ChatGPT URL supplied no readable conversation; the kickoff and latest
explicit instructions remain the product authority. Earlier access failures are
historical evidence, not current claims that Git, Docker or Ollama are absent.

## Smallest vertical slice and proof

Task: “Create a draft invoice for customer CUST-001 for two hours of SVC-CONSULT,
dated 2026-11-07, due 2026-11-21. Do not send it.”

The Go agent exposes all three authorized smoke tools and calls the exact verified
installed Qwen model through native Ollama. The Python evaluator inspects persisted
state independently. Success is exactly one USD draft for CUST-001, one line of
quantity 2 × 12,500 cents, subtotal/total 25,000 cents, tax zero, correct dates and
no unrelated writes. The final answer identifies the saved draft. Replaying its
idempotency key must return the same invoice without another row.

Before grading, revoke agent execution access and establish that already-authorized
writes have completed or rolled back and cannot commit later. Preserve the immutable
agent-only snapshot and original answer verdict before any replay. A separate trusted
verifier may replay only an already-passing original request; verification cannot
create a missing invoice or repair a failed attempt. Revoke and settle verifier
access before a second snapshot and reset. Unknown settlement yields
`settlement_unknown`, fails the smoke/comparison-validity gate and quarantines the
run without unsafe reset or reuse. Post-agent settlement/verification has its own
30-second ceiling, recorded separately from the 300-second agent task deadline.

The future T040 harmless Ollama capability probe runs only after admission and
active-goal runtime authorization. Metadata or a successful probe cannot replace T023's
real MCP-backed invoice proof. Scripted-model tests remain distinct from live Qwen.

## Reading map and deferred work

- [TASK_GRAPH.md](TASK_GRAPH.md): dependency/status authority and acceptance criteria.
- [EXECUTION_PLAN.md](EXECUTION_PLAN.md): waves, exclusive files and role assignments.
- [Shared wave assumptions](WAVE1_CONTRACT_ASSUMPTIONS.md): T003–T005 design baseline;
  T006's versioned machine-readable contracts remain future work.
- [EVALUATION_PLAN.md](EVALUATION_PLAN.md): fixtures, reset/oracle and measurements.
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md): resource admission and stop policy;
  its old coarse sequence is superseded by the DAG.
- [NODE1_AUDIT.md](NODE1_AUDIT.md): observed facts, access blockers and remaining checks.

Defer OpenTelemetry/Jaeger to v2, retrieval implementation until its baseline gates,
large synthetic catalogs until scale validation, and concurrent inference until a
separate capacity review. Real ERP APIs/data, invoice sending, public endpoints,
driver repairs and native Ollama tuning are outside current scope.
