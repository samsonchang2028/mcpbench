# MCPBench project context

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
All service names, ports and budgets there are proposals pending admission.

## Current status — 2026-11-07

This is a documentation scaffold. The user authorized parallel documentation-only
T003/T004/T005 despite blocked Git and host runtime access. No application code,
Compose implementation, dependency installation, model pull or inference is
included in this wave. The orchestrator records review/test evidence and task
status; these documents do not imply the tasks or milestones have passed.

The [audit](NODE1_AUDIT.md) records a Dell Precision 5520, i7-7820HQ and Quadro M1200
PCI device; GPU usability is unverified. Immich, Jellyfin and other workloads were
reported by the user; Docker inventory, ports, Ollama server/model identity and
residency remain unverified because session access was denied. Permission errors
are not evidence that services are absent or unhealthy.

Git initialization previously failed because `.git` is read-only; no valid Git
repository or commit is claimed. Do not relocate metadata to bypass restrictions.
The shared ChatGPT URL supplied no readable conversation; the kickoff and latest
explicit instructions are the product authority. Missing runtime evidence and
resource admission remain blockers, even if a short resource sample looks idle.

## Smallest vertical slice and proof

Task: “Create a draft invoice for customer CUST-001 for two hours of SVC-CONSULT,
dated 2026-11-07, due 2026-11-21. Do not send it.”

The Go agent exposes all three authorized smoke tools and calls the exact verified
installed Qwen model through native Ollama. The Python evaluator inspects persisted
state independently. Success is exactly one USD draft for CUST-001, one line of
quantity 2 × 12,500 cents, subtotal/total 25,000 cents, tax zero, correct dates and
no unrelated writes. The final answer identifies the saved draft. Replaying its
idempotency key must return the same invoice without another row.

The future T040 harmless Ollama capability probe runs only after admission and
separate runtime approval. Metadata or a successful probe cannot replace T023's
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
