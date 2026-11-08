# Security and resource contract — v1

Current authorization: the active v1 goal permits routine eligible DAG work,
including admitted runtime tasks, without repeated per-wave approval. This changes
no security boundary, resource threshold or stop condition. Earlier doc-only wave
limits are historical; T001 still blocks full runtime admission.

Status: T005 documentation candidate. These are required design/test behaviors,
not claims that benchmark containers, authorization or full admission have passed.
Follow [AGENTS.md](../AGENTS.md), the shared
[wave assumptions](WAVE1_CONTRACT_ASSUMPTIONS.md) and the admission/stop policy in
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). The current wave permits only
documentation. Application implementation, Docker mutations, dependency installs,
model pulls and live Ollama calls remain blocked.

## Permission-refresh evidence and remaining boundary

The [2026-11-07 audit](NODE1_AUDIT.md) supersedes the earlier broad access blockers.
Normal Git initialization/index/commit writes succeeded (baseline `e0ce746`),
Docker inspection works through sfkim's existing docker-group membership, and
native Ollama metadata is reachable. These are control-plane capabilities only;
they grant no additional permission to a future benchmark agent.

The installed `qwen3.5:9b` is Q4_K_M and advertises tool support; the inspected
loaded-model list was empty. Metadata and an idle snapshot do not prove valid tool
calls, exclusive access during a future trial, or T040 success. Model-storage
target/symlink/filesystem verification remains blocked: sfkim cannot traverse the
service-account model directory and noninteractive sudo requires authentication.
Parent-directory free space does not prove the actual model target's free space.

Preserve that ordinary Unix boundary. Do not change ownership, permissions, groups
or sudo policy, mount protected host files into a container, or use Docker/privileged
execution as a workaround. An authorized service-account check must supply the
missing storage evidence. T001 therefore remains narrowly BLOCKED even though
the former sandbox/socket restrictions have been lifted. Historical evidence
supports sandbox restrictions as the main earlier cause, without proving that
every Unix permission was unchanged.

The audit also records NVIDIA kernel driver 580.173.02 versus NVML 580.178
(`driver/library version mismatch`) and an existing unhealthy
`immich_machine_learning` container. Neither is repaired by this project. GPU
offload is unverified; any CPU feasibility claim needs the later admitted probe.
Compare service health against the recorded baseline, distinguishing an existing
unhealthy state from a new regression; do not conceal deterioration or restart the
service to obtain a cleaner baseline. Existing workloads have no inspected hard
CPU/memory quotas, so low current usage does not reserve future capacity.

## Principals and separation of authority

Codex development access, trusted evaluation control-plane access and benchmark
agent runtime permissions are different capabilities. A developer's ability to
inspect a file or issue a host command never grants that capability to the agent.
Billing records are fictional, project-local fixtures. Secrets, including synthetic
DB passwords and run capabilities, live only in ignored trusted configuration or
runtime secret delivery, never fixtures, prompts or logs. No production accounting
integration or sending/payment action is authorized.

| Principal/process | Permitted access | Explicitly excluded |
| --- | --- | --- |
| Authorized host operator / Codex orchestrator | Approved MCPBench planning files; host discovery when session permissions permit; future scoped container lifecycle after gates | Changing existing services/volumes, bypassing sandbox/Git restrictions, changing native Ollama configuration or drivers |
| Trusted host-side launcher | Future fixed evaluator-prepare → agent-execute → evaluator-grade/reset lifecycle; admitted resource monitoring; bounded run-specific input/output transport | Model-selected commands, images, paths, environment variables or launches; Docker socket mount into either container |
| Python evaluator preparation/reset | Project-owned PostgreSQL on private network; create/seed/drop only registered per-run DB/schema; expected states and durable evaluation artifacts | Existing application databases/volumes; delegating reset/admin rights to the agent |
| Independent grader | Read-only snapshot/queries of the registered run state plus versioned expected-state fixtures | Writing invoices or basing correctness solely on agent prose/tool responses; grading a different run's state |
| Trusted replay verifier | Separate short-lived capability for at most two verification calls against the already-correct settled run/request: same-key/same-payload replay and changed-payload conflict | Agent access to verifier capability; creating a missing draft, repairing failed task state, selecting another run/request or extending agent execution |
| MCP service | Restricted project DB connection; registered run routing; allowed billing reads and atomic draft writes after per-call ACL checks | Database/schema creation, reset, arbitrary SQL, cross-run access, invoice sending/payment or production API calls |
| Go agent | Sanitized task, authorized schemas, run-scoped synthetic capability and fixed native Ollama/MCP endpoints; write own bounded event/result files | DB credentials, expected states, grader/reset APIs, Docker socket, privileged mode, shell/file/network tools or arbitrary outbound URLs |
| Model | Task/history and authorized tool schemas/results; propose tool names and schema-valid billing arguments | Principal, tenant, run routing, idempotency key, credentials, endpoints, budgets or process configuration |

One evaluator container may implement preparation, grading and verification, but
its grader connection must be read-only and separate from reset credentials and
verifier capability. Keep reset, grading and verification code paths distinct and
test that grading never mutates the database. The verifier makes only constrained
MCP requests under its own capability; it cannot borrow reset/admin credentials.
Server SQL permissions must be least privilege for the registered run. Exact
role setup, connection lifecycle and wire schemas are frozen at T006 and exercised
at T018–T020; their absence keeps runtime admission incomplete.

## Billing authorization and trusted routing

V1 uses two synthetic runtime principals. `billing-reader` can invoke authorized
read tools; `billing-drafter` has those reads plus `billing_create_draft_invoice`.
Initially the reads are `billing_list_customers` and `billing_list_items`; the
seven read tools added for the ten-tool baseline are subject to the same rules.
Neither principal has schema/reset, send, pay or arbitrary-query rights.

Every MCP call requires trusted authentication and server-side permission checks,
including calls bypassing the Go agent. Missing, invalid, expired or mismatched
capabilities fail closed before DB reads/writes. Catalog filtering and model
instructions supplement this enforcement; neither is an authorization boundary.
Denied calls return bounded errors and generate a sanitized denial event.

The trusted control plane creates an immutable mapping of an opaque per-run
capability to `(run_id, tenant_id, principal, allowed tools, registered DB/schema,
expiry)`. The MCP service resolves routing only through that mapping. It must not
concatenate a model/header-supplied schema or trust a caller-asserted principal.
No unregistered database/schema may be selected. A capability valid for run A
cannot read or write run B, even when both belong to the same fictional tenant.
T006 specifies the auth transport and mapping provisioning/revocation format;
those formats must preserve this invariant rather than allow self-asserted access.

The trusted launcher carries only the agent's run-scoped capability and metadata;
keep them outside prompts, tools, model-visible history, logs and fixtures. Revoke
agent access at result/deadline, before taking the authoritative agent-only snapshot.
Revocation blocks new calls but is not proof that already-authorized DB operations
have completed. The bounded settlement rules below apply before both snapshots
and before resetting or reassigning run storage.

Idempotency metadata comes from the trusted launcher/agent envelope, never model
arguments. Scope uniqueness to tenant/run/request identity. Identical key and
normalized payload return the same saved draft; a changed payload conflicts.
The server reads canonical prices and validates cents, dates, quantities and
draft-only state within an atomic transaction. A denied or invalid request leaves
no partial invoice or unrelated mutation. Retry after an ambiguous timeout retains
the same key; retries cannot obtain a fresh execution budget.

## Terminal-state fence, grading and verification

1. Stop the agent at result/deadline, preserve output/events/exit status and revoke
   its execution capability. A process exit alone does not settle MCP writes.
2. Establish within the settlement budget that every already-authorized operation
   completed or rolled back and cannot later commit. T006 freezes the actual
   fence/drain protocol and how settlement evidence is produced. Missing evidence,
   an unresolved operation or a timeout yields `settlement_unknown`: comparison
   invalid, smoke gate failed, evidence retained and run quarantined. A diagnostic
   snapshot is not authoritative PASS. Do not reset, reuse or reassign storage
   while an authorized operation might still commit.
3. Preserve an immutable settled **agent-only** snapshot, then independently grade
   original database state, final answer and execution outcome. This is the task's
   authoritative correctness evidence; no verification call may precede it or
   overwrite it. A failed/timeout task cannot be rescued by later verification.
4. Only after the original task gate passes, issue a separate trusted verifier
   capability, never visible to the agent. Constrain it to the settled run/request
   and existing invoice. Permit same-key/same-payload replay and changed-payload
   conflict checks only. Verification must not create a missing invoice or repair
   incorrect state: assert same saved invoice ID and zero application-state change.
5. Revoke verifier access, fence/drain again, and save an immutable final settled
   snapshot. Compare it to the original agent-only application state and grade
   replay/no-extra-write invariants. Any unexpected late change fails verification;
   unknown settlement additionally invalidates the comparison and quarantines the
   run. Preserve original task correctness separately even when verification fails.
6. Persist both snapshots and all outcomes, then perform only scoped reset and
   check the seed fingerprint. Reset/reuse requires revoked capabilities and
   evidence that no agent or verifier write can later commit. Uncertain settlement
   forbids reset; quarantine instead of attempting cleanup that races a write.

Post-agent settlement/verification is capped at **30 seconds total**, **5 seconds
per settlement, verification or DB operation**, at most **two verifier calls** and
**no verifier retries**. This budget is outside the 300-second agent task deadline,
never extends it and never rescues a timeout. Record and charge its full latency/
compute separately and include it in full-lifecycle totals identically for every
strategy. Exceeding these bounds is explicit failed verification; if settlement
cannot be established, also emit `settlement_unknown` and quarantine. T006 must
freeze capability restrictions, lifecycle fields and error/event definitions that
enforce these rules before implementation.

## Network, process and artifact boundary

The Python evaluator resides on the private project network with direct benchmark
DB access. PostgreSQL publishes no host port. The MCP server uses that network
for DB access and publishes only `127.0.0.1:18081` (candidate, observed free during
the audit but requiring a fresh ownership/listener check before startup).
The agent uses host networking to reach loopback Ollama `127.0.0.1:11434` and MCP;
it opens no listener. No endpoint is publicly published, and no existing network
or application volume is attached. Validate Host/Origin and bounded MCP bodies;
an accepted HTTP request still needs independent per-call authentication.

Host networking exposes other host destinations at the OS network layer. Fixed
endpoint allowlists, no arbitrary URL tool, no shell tool, non-root execution,
dropped capabilities and read-only root filesystem reduce accidental/model-driven
access; they do not prove OS egress isolation against compromised code. V1's
residual risk assumes trusted pinned application images/code. A stronger network
relay/egress boundary is a later design review, never an automatic reason to rebind
or reconfigure native Ollama. Record this limitation in results and review.

The trusted launcher runs fixed allowlisted images/commands and sanitized env;
it never builds shell commands from model text. The bounded, versioned request/
result envelope may use stdin/stdout or run-specific paths, with exact transport
frozen at T006. Reject path traversal, symlinks escaping the assigned run, unknown
envelope fields and oversized inputs before launch. A run ID identifies a mapping,
not permission to choose host paths or database names.

Mount only the agent's sanitized request read-only and its own event/result output
directory writable. Expected states, snapshots, evaluator credentials and parent
artifact directories are absent from its namespace. Neither evaluator nor agent
gets privileged mode, host PID namespace, GPU privileges, Docker socket or broad
host filesystem mounts. Use non-root users, `no-new-privileges`, dropped capabilities,
read-only root filesystems and bounded temporary storage. T015 freezes exact
mounts/users/limits; T020 tests both configuration and observed runtime permissions.

V1 observability is structured JSONL with run IDs, call IDs and deterministic
artifacts; OpenTelemetry, Jaeger and collectors are v2. Redact synthetic capability
tokens and DB passwords just as real secrets. Retain failed-attempt evidence,
config/model/catalog/fixture hashes and reset fingerprints outside run DB cleanup.
Cap smoke-run artifacts at 100 MiB; a write/cap failure marks evidence incomplete
and cannot silently become a successful benchmark result.

## Admission and resource budgets

T001 is an authorized read-only host audit. T007 requires completed T001/T006,
known model identity/residency/shared use, known resource ownership and free ports,
and fresh capacity evidence. Permission denial is an unresolved observation,
not proof that a daemon, model or application is absent. Preserve existing
homelab services, volumes, drivers and native Ollama; do not unload shared models.

Before any later admitted build/start/inference operation, require >=20 GiB RAM
available and >=20 GiB free on the project, Docker and model filesystems, plus
a 60-second sample with no sustained swapping and no existing-service health
regression. Treat any three consecutive sampling intervals with swap-in or
swap-out as sustained activity; exclude vmstat's cumulative first row. The short
historical audit did not satisfy this gate. The refreshed 60-second sample has
30 two-second intervals, no swap-in/out and 90–94% idle CPU; about 25 GiB RAM was
available. This meets only the sampled no-sustained-swap/resource components,
not T007 as a whole. Actual model-storage free space, T006 contracts and fresh
point-of-execution ownership/health/loading checks are still prerequisites.
The observed 229 GiB free on the project, Docker-root and model-parent filesystem
cannot substitute for the inaccessible model target's verification.
Confirm model sharing/residency can
accept the request without displacing another active workload, or leave it blocked.

| Component | Proposed memory cap | Proposed CPU quota |
| --- | --- | --- |
| PostgreSQL | 512 MiB | 0.5 CPU |
| Go MCP service | 256 MiB | 0.5 CPU |
| Go agent | 512 MiB | 1 CPU |
| Python evaluator | 512 MiB | 0.5 CPU |

Use up to five DB connections per service pool and one attempt at a time. Serialize
costly operations through the orchestrator's resource lease. Proposed native
model RAM is 8–12 GiB until measured; Ollama is outside container caps. If actual
requirements exceed the estimate, recalculate admission before proceeding.
Container OOM is failure evidence, not permission to raise limits during a trial.

Proposed request budgets: supported context 4096 tokens, output cap 512,
temperature 0, recorded supported seed/thinking/keep-alive settings without global
changes; <=8 model turns and <=12 tool calls; 5-second DB/tool deadlines,
120-second model deadline, 300-second task deadline and at most one transient
retry inside the same total budget. Do not silently truncate tool schemas or
increase budgets after observing a strategy's result. Use monotonic clocks for
duration and UTC timestamps for correlation; record unavailable metrics as null.

During a later live call sample every two seconds. Abort only the MCPBench agent/
attempt if RAM available is below 8 GiB for three consecutive samples, swap-in/out
persists for three samples, any project container OOMs, or an existing service
shows a new health regression. Record interruption and preserve evidence. Stop
only verified owned project containers if necessary, retain volumes, and continue
observation: cancellation need not immediately release Ollama's memory. Never
force unload, clear swap/cache, change drivers, or restart another service.

## Early Ollama capability probe T040

T040 requires successful fresh T007 admission and active-goal runtime authorization;
the documentation-wave approval does not authorize it. Use the exact installed
model tag/digest and one bounded native chat request with a harmless `probe_echo`
tool. Validate returned tool name and strict JSON arguments, then compute the
echo locally. No arbitrary code or billing/MCP write is involved. A missing,
unknown or malformed call is a failed capability probe, even if `/api/show`
advertises tool support. Save response and resource evidence in the probe-owned
artifact path; redact auth material. No pulls, config changes, forced unloads or
automatic retries. Probe success does not prove end-to-end T023 invoice success.

## Negative test contract for later admitted tasks

These are required expected behaviors, not tests executed in this wave.

| Case / owning gate | Expected observable outcome |
| --- | --- |
| Reader calls draft tool; direct MCP bypass of agent / T013,T020 | Authorization error, sanitized denial event, zero writes |
| Missing/expired capability, forged principal or cross-run route / T013,T020 | Reject before exposing run data, zero writes, no fallback to default tenant/schema |
| Model supplies URL, shell text, reset/schema/header fields / T014,T020 | Reject unknown/unauthorized arguments or treat content as data; no new endpoint, process or reset action |
| Agent attempts grader file/DB/reset access / T015,T020 | No mounted expected-state/credential files or DB credentials; grader/control actions unavailable; distinguish this from the documented host-network residual risk |
| Invalid item/date/quantity/price; failure mid-write / T012,T019 | Bounded validation/execution error and no partial draft; unrelated seed data unchanged |
| Duplicate/concurrent calls; timeout after commit / T012,T019 | Exactly one draft, same key/payload returns same ID, changed payload conflicts |
| Agent exits/reaches deadline with a pending write / T019,T020 | Revoke new-call access, fence/drain before agent-only snapshot; unknown settlement yields `settlement_unknown`, invalid comparison/failed smoke gate and quarantine, with no reset/reuse |
| Original invoice missing or original task fails / T019,T020 | Preserve original failed grade; no replay capable of creating a draft, no repair of state and no overwrite of agent-only evidence |
| Agent attempts verifier capability; verifier selects another run/request / T019,T020 | Capability absent from agent namespace; unauthorized request denied, zero writes |
| Replay/conflict checks followed by late verifier write / T019,T020 | Revoke verifier then settle before final snapshot; changed application state fails verification, unknown settlement invalidates comparison and forbids reset |
| Verification exceeds 30 seconds total/5 seconds per operation, attempts a third call or retries / T019,T021 | Reject/stop at shared limit; verification fails, record separate lifecycle costs without extending agent deadline; quarantine if writes cannot be proven settled |
| Stale/failed reset or uncertain in-flight write / T010,T018,T019 | Do not start next run; retain evidence and quarantine run; no global cleanup and no reset while writes may remain live |
| Extra rows or wrong customer/status/total / T010,T018 | Independent DB oracle fails even if model claims success |
| Oversized envelope/log, escaped mount/path, injected env / T015,T019,T021 | Launch/input failure or explicit incomplete evidence, no path escape, preserved bounded summary where possible |
| Public binding, privileged mode, Docker socket or external volume / T015,T020 | Configuration gate fails before startup; actual binding/ownership checks must also pass after approved startup |
| Pressure, container OOM, timeout or cancellation / T022,T023 | Abort/timeout outcome, all attempt costs retained, owned cleanup only, no automatic host repair |
| Tool metadata present but no valid model call / T040 | Probe FAIL/unsupported outcome, never a fabricated capability PASS |

## Completion evidence and remaining freeze boundary

T005 can be reviewed as documentation when the policy, matrix, budgets and expected
tests agree with T003/T004 and shared assumptions. T006 must still freeze executable
schemas, auth/run mapping, request/result transport, launch/mount allowlists and
error/event definitions. Its absence blocks implementation and all runtime claims.
This refresh uses the recorded audit; the documentation implementer performed no
host checks, application tests, probes, Docker operations or service changes.
