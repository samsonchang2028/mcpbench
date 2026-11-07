# Dependency-aware implementation plan

Scheduling update (2026-11-07): [TASK_GRAPH.md](TASK_GRAPH.md) is now the
authoritative task DAG and [EXECUTION_PLAN.md](EXECUTION_PLAN.md) assigns waves,
ownership and review gates. The coarse sequence below is historical; retain the
admission/stop policies here. The new graph schedules reconciliation of the older
Go-evaluator/three-tool-only design with the kickoff's Python evaluator and
ten-tool baseline, preserving the three-tool smoke slice. User-approved T003–T005
documentation assignments may run while Git/runtime access are blocked; this
exception authorizes no application implementation or runtime operations. V1 uses
JSONL artifacts; OpenTelemetry and Jaeger are deferred to v2. T040 is the future
early capability probe after admission and before T008, requiring separate approval.

Current permission refresh: normal Git initialization/commit and read-only Docker/
Ollama inspection now work. T001 remains narrowly blocked on the actual model-store
filesystem under the ollama account; T006/T007/T040 are incomplete. The coarse rows
below are historical future-work planning, not completed application work.

```text
P0 host audit + Git access
 └─ P1 pin contracts/dependencies/Compose design
     └─ P2 database + billing domain
         └─ P3 MCP server
             └─ P4 agent + trace + independent oracle
                 └─ P5 constrained stack validation
                     └─ P6 one live Qwen draft
                         └─ P7 baseline evidence and later retrieval design
```

| ID | Depends on | Deliverable and acceptance criteria | Validation gate |
| --- | --- | --- | --- |
| P0 | None | Complete missing audit in NODE1_AUDIT.md; confirm project name/subnet/port ownership, Docker/model storage and capacity, current Ollama consumers/loading, exact model capabilities; initialize Git once host metadata is writable | Evidence saved; no displaced workloads; valid Git repository; launch gate below passed |
| P1 | P0 | Pin Go/toolchain, official MCP SDK, PostgreSQL image digest and module dependencies; define three schemas and seed/oracle fixtures; design Compose project, limits and runner profile | SDK/protocol/model compatibility checked against primary docs; schema and network review; no production credentials |
| P2 | P1 | Versioned migrations, repeatable seeds, transactional billing and idempotency; separate test database | Deterministic integration tests pass for money, validation, rollback, duplicate and concurrent writes; seed twice is stable |
| P3 | P2 | Go MCP service with initialization, list/call, bounded errors and health/readiness | Real MCP client exercises all three tools; origin/host and input validation pass; no public publication |
| P4 | P3 | Small Go Qwen loop, full-context tool adapter, Python evaluator, fixed endpoints, call/time budgets, JSONL artifacts and independent database oracle | Scripted-model tests prove routing/history/error budgets; real MCP path persists expected draft using scripted calls; no fabricated live-Qwen result |
| P5 | P4 | Render and validate Compose; build sequentially; start only owned database and MCP; verify ephemeral runner connectivity without inference | Limits present, seed-ready health, loopback binding and no DB publication confirmed; existing services retain baseline health |
| P6 | P5 | One live request using exact verified Qwen tag/digest, monitored throughout | Tool calls execute through MCP, oracle sees correct single draft, replay is idempotent, artifacts complete, resource limits respected |
| P7 | P6 | Record result, limitations and reproducible commands; define later selector interface and comparison protocol | One honest baseline report; all failures retained; no claims comparing unimplemented strategies |

## Admission before builds or startup

Refresh resources immediately before work. Initially require at least 20 GiB
available RAM for the conservative model-plus-stack budget, 20 GiB free on the
project/Docker/model filesystems, no sustained swap-in/out over a 60-second sample,
and no existing-service health regression. If the observed model needs more than
12 GiB or concurrent workloads consume the reserve, recalculate before launching.
Capacity estimates in ARCHITECTURE.md are hypotheses, not permission to overcommit.

Inventory must establish that project name `mcpbench` and its planned volume/network
names are unused, chosen subnet does not overlap existing networks, and candidate
18081 is free. Confirm Ollama 11434 is the intended local listener, exact Qwen
model is installed with tool support, and its current residency/shared usage are
known. Never pull a replacement model automatically because a tag was guessed.
Confirm that an additional request will not evict another active workload's model;
if this cannot be established, leave live inference gated.

Record existing container status and resource stats. Compose operations must use
the explicit file and project name and affect only resources verified as owned by
this project. Require resource-limit and local-port inspection of the rendered
Compose config before `up`. Build one image at a time; native Ollama remains
outside the Compose project.

## Stop conditions and recovery

During the first model call, sample resources every two seconds. Abort the runner
if available RAM remains below 8 GiB for three samples, swap-in/out persists over
three samples, any MCPBench container is OOM-killed, or an existing service develops
a health regression. Record the condition and inspect owned logs; do not repair
the host or restart existing services. A safety abort is a failed/interrupted run.
Cancellation may not immediately release Ollama memory; keep observing and do not
force model unloading or change the shared service.

On tool timeout after a possible commit, retry with the same idempotency key or
query the run's persisted state. Preserve database and trace evidence. Stop only
the MCPBench runner and, if needed, its verified owned service containers; retain
volumes. Investigate via deterministic tests before another live call.

## Completion of this setup assignment

Required documentation and a reviewable plan are present. No heavy workloads have
launched. The audit is explicitly partial, and a valid Git repository cannot be
claimed until the protected `.git` mount is writable. These host-access blockers
must remain visible in the handoff rather than being silently bypassed.
