<!-- Current access refresh supersedes historical snapshot/status prose below. -->
# MCPBench task graph

Current status:17 tasks DONE, including corrected billingT012,agentT014 and
lifecycleT016 source. T013 MCP server is implementing. T018 final runtime gate
is BLOCKED on available RAM below20GiB;initial real ownedDB tests passed but
independent repetition is UNRUN. No runtime/inference gate is waived.
The older access observations below are historical.

Snapshot: 2026-11-07. Planning only; no implementation dispatched. This graph
supersedes the coarse P0–P7 task sequence in IMPLEMENTATION_PLAN.md; that file's
resource admission and stop conditions still apply. Its P0 labels are old phase
labels, not the priority ratings below.

## Authority, scope and current evidence

The user's **MCPBench — Node 1 Project Kickoff** specification is the product
source of truth. Research question: how MCP tool retrieval affects task success,
latency, token usage, cost and reliability as catalogs scale. Compare full context,
semantic top-k, hybrid (authorization/metadata, keywords and vectors), and
hierarchical domain selection without assuming a winner. Same permissions,
fixtures, model settings and execution budgets apply to every strategy.

The earlier architecture needs reconciliation: retain the three-tool invoice
smoke slice, then establish ten executable tools before growing synthetic catalogs.
Use a Go MCP service, small Go model agent, **Python evaluation runner**, PostgreSQL,
structured JSONL logs with run IDs and deterministic artifacts, native Ollama,
and isolated Compose resources. OpenTelemetry and Jaeger are deferred to v2.
Python owns reset/execute/grade/artifact orchestration; the Go agent owns
model conversations and model-facing MCP schemas. The trusted launcher carries
process transport only; server/catalog/grader code may inspect schemas as needed. Evaluation credentials never reach the agent.

Read-only refresh at 14:23 America/Los_Angeles confirmed i7-7820HQ (4 cores/8
threads), Quadro M1200 PCI device, 30 GiB usable RAM/25 GiB available, 3.6 GiB swap
used, 229 GiB project disk available, load 0.39/0.49/0.46. Two one-second samples
had zero swap-in/out and 93–94% CPU idle; memory PSI averages were zero. Docker
inventory, ports and Ollama tags/loaded models remain denied by session access;
`nvidia-smi` cannot communicate with the driver, cause unverified. These are not
proof that host services are absent. Git reports no valid repository and `.git`
is read-only. Existing files are planning docs and AGENTS.md; no application,
Compose or separate tasks/ index exists. This is historical audit evidence;
state/CURRENT.md and documentation context/reservation files were created for the
approved wave. No builds or inference were run.

## Task semantics

Priority: P0 = safety, validity or prerequisite blocker; P1 = first baseline and
credible comparison; P2 = later resilience/reporting. Status: READY = dependencies
complete and current access sufficient; IMPLEMENTING/CANDIDATE = assigned or
frozen documentation work; DONE = integrated with required validation evidence; BLOCKED = named external limitation;
WAITING = prerequisites unfinished. No application implementation task is done; documentation outcomes are recorded below.
Documentation-only T003–T005 assignments are expressly permitted while Git and
host access are blocked, using exclusive writable paths and content hashes. This
exception permits no application code, dependency installation, Docker operations
or live Ollama execution. Dependencies are AND edges. Re-run time-sensitive admission immediately before
costly actions even if an earlier gate passed. Apply
[task-classifier](../agents/task-classifier.md): LIGHT maintenance needs one
implementer, a focused check and orchestrator integration; FULL tasks need a
frozen candidate and independent review/test evidence before DONE. Explicit row
acceptance gates always apply. Reviewers/testers are distinct roles and inspect
the frozen candidate while its author pauses edits. Routing changes no task IDs,
dependencies, statuses or resource/security gates.

Role codes: O orchestrator/integrator, H authorized host operator, C contracts,
E Python evaluation, D database/billing, M MCP service, A Go agent/retrieval,
I infrastructure/telemetry, R independent reviewer, V independent tester.
Each row names its implementing role; R reviews FULL candidates and V validates
them. H alone supplies inaccessible host observations; O alone owns shared manifests,
state, task statuses and merges. Roles are assignments for later dispatch, not
claims that workers are currently running.

## Nodes and explicit dependencies

| ID | Task / implementer | Depends on | Priority | Status | Objective acceptance / evidence |
| --- | --- | --- | --- | --- | --- |
| T001 | Finish read-only host audit / H | — | P0 | DONE | Authorized host evidence for Docker workloads/limits/health, published ports, networks/volumes, storage roots/free space, Ollama listener/server/tag/digest/quantization/capabilities and residency; no service changes. Authenticated host model-path/df output plus fresh inventory integrated at b845082; independent R APPROVE/V PASS in state/reviews/T001-T007-*.md. No Unix boundary bypass. |
| T002 | Enable normal Git metadata / H,O | — | P0 | DONE | Host makes project `.git` writable without bypass; `git rev-parse --show-toplevel` resolves this path and clean initial planning commit recorded; no unrelated files staged. Normal initialization and baseline commit e0ce746 succeeded; independent reviewer APPROVE and tester PASS, normal task commits integrated. No remote/push. |
| T003 | Reconcile product/architecture specification / C | — | P0 | DONE | PROJECT_CONTEXT and ARCHITECTURE specify Go agent versus Python evaluator, three-tool smoke versus ten-tool baseline, native Ollama, scope and all four unchanged strategies; record decisions and remaining measured assumptions. |
| T004 | Define evaluation contract before code / E | — | P0 | DONE | EVALUATION_PLAN defines fixture/task/trace/result schemas, reset lifecycle, database oracle, exact success/failure labels, required-tool sets, metric formulas and missing-data handling; fixed invoice oracle retained. |
| T005 | Define security/resource contract / I | — | P0 | DONE | Written principal/permission matrix, credential and network boundaries, scoped reset, timeout/retry budgets, host-network tradeoff, resource admission/stop policy and negative tests; agent has no grader/admin credentials or Docker socket. |
| T006 | Freeze cross-component contracts / C,O | T003,T004,T005 | P0 | DONE | Versioned JSON schemas in contracts/ for catalog/tools, task fixtures, agent request/result, trusted principal/run-context routing, trace and grading; three smoke tools and ten baseline tools have input/output/error/authorization definitions; ambiguity resolved and R/V sign off. |
| T007 | Runtime admission evidence / H,I | T001,T006 | P0 | DONE | IMPLEMENTATION_PLAN admission met: 60-second resource sample, >=20 GiB available RAM and >=20 GiB free on relevant filesystems, no sustained swapping/regression; unused project/subnet/ports, model residency/shared use known. Recalculate model budget if >12 GiB. Metadata capability check only; T040 verifies basic tool output early and T023 verifies the real MCP invoice later. Evidence: state/audits/2026-11-08-admission.json, candidate 8ca7669, R APPROVE/V PASS; immediate pre-call refresh still required. |
| T040 | Early Ollama capability probe / H,A,V | T007 | P1 | DONE | Exact installed Qwen/digest, one bounded native chat with harmless probe_echo, strict name/JSON args and local echo verified. Attempt01 safety-aborted and retained; user explicitly approved one gated retry. Attempt02 passed in20.174s after fresh60.034s admission, 4096/512 limits and2sec monitoring; no sustained swap or service regression. R APPROVE/V14-check PASS: state/reviews/T040-retry-*.md. Immutable artifacts/probes/t040-20261108-02/hashes.json; summary state/audits/2026-11-08-T040-retry-result.json. Native tool capability only; no billing/MCP success claim. No further inference request authorized by this one-retry approval. |
| T008 | Repository skeleton and pinned dependencies / O | T002,T006,T007,T040 | P0 | DONE | Go module, Python project/lock, chosen SDK/protocol and image digests pinned; empty package boundaries and check commands agree with contracts; dependency resolution/build is admitted by explicit T007 dependency. Candidate faaadeb2 integrated95d5a7c; R APPROVE/V PASS in state/reviews/T008-*.md:46 tests,fixture CLI,locks,compile/vet,stub exits and4 official image metadata hashes. No runtime startup/inference. |
| T009 | Versioned fixtures and expected states / E | T006 | P0 | DONE | eval/fixtures contains three-tool invoice fixture, baseline fictional customers/projects/items/timesheets and expected states; valid/invalid fixture contract checks; no runtime/model dependencies. |
| T010 | Independent grader and reset tests first / E | T008,T009 | P0 | DONE | eval/grading and eval/reset tests cover correct and deliberately wrong customer/price/status/date, extra writes, stale state and failed reset; grader consumes database snapshots, not model prose; unimplemented DB path explicitly unrun until T018. Candidate7ac9006 integrated0bc049f;R APPROVE/T010-reviewer-v2.md,V PASS/T010-tester.md. Actual DB/container runtime remains UNRUN under later gates. |
| T011 | Migrations and seed / D | T008,T009 | P0 | DONE | db/ versioned schema and repeatable seed match contracts, foreign keys, money and idempotency constraints; tests authored for seed twice, migrate existing volume and rollback; live validation at T018. Candidatee0ccb15 integratedfa76565;R APPROVE/T011-reviewer-v2.md,V PASS/T011-tester.md. Actual DB/container runtime remains UNRUN under later gates. |
| T012 | Draft billing domain / D | T010,T011 | P0 | DONE | internal/billing and repository code calculate cents, reject invalid dates/IDs/quantities and unknown fields, create atomically and enforce same-key replay/changed-payload conflict; unit tests pass, PostgreSQL cases await T018. Corrected candidate independently R APPROVE/V cached tests PASS; live Go/MCP workflow remains T019/T023. |
| T013 | Three-tool MCP adapter / M | T012 | P1 | IMPLEMENTING | cmd/billing-mcp + internal/mcp implement pinned 2026-07-28 discovery/negotiation and tools/list/call, three exact schemas, Host/Origin checks, server-side per-call ACLs and trusted run-context routing to the evaluator-owned isolated DB/schema, bounded results and errors; real MCP client tests authored. |
| T014 | Full-context agent loop / A | T008,T010 | P1 | DONE | cmd/agent + internal/agent, internal/ollama implement all authorized schemas, transcript/call correlation, trusted idempotency metadata, fixed endpoints, budgets and bounded retries; scripted-model tests reject invalid/unknown/unauthorized calls without executing them. Corrected candidate independently R APPROVE/V cached tests PASS; live Go/MCP workflow remains T019/T023. |
| T015 | Safe Compose/configuration / I | T008,T005 | P0 | DONE | compose.yaml and containers/ define separate project/volume/internal DB, loopback MCP candidate 18081, non-root agent with no listener, CPU/RAM limits, no privilege/socket/external volumes; render/static checks pass without startup. Candidatea5c0096 integrated039f990;R APPROVE/T015-reviewer.md,V PASS/T015-tester.md. Actual DB/container runtime remains UNRUN under later gates. |
| T016 | Python lifecycle and artifacts / E | T010 | P0 | DONE | eval/runner runs reset-check-execute-snapshot-grade-save-reset; failed reset blocks execution and records failure; per-run DB/schema isolation with scoped cleanup, persisted artifacts outside reset scope; scripted agent process contract tests pass. Corrected06ccb00 integrated9d56836;R APPROVE/V49testsPASS;realbackend/CLItransport remains T018/T019. |
| T017 | Structured JSONL instrumentation / I | T008,T006 | P1 | DONE | observability/ library/adapters define correlated JSONL events with run/call IDs for retrieval/model/MCP/DB, redaction, monotonic durations and durable local artifacts, trace-size cap; logging failure preserves summary where possible and marks artifacts incomplete; no OpenTelemetry, Jaeger or collector in v1. Candidated443fee integratedad6833f;independentR APPROVE/V PASS inT017-reviewer.md/T017-tester.md. Go full-validatorcallback required;runtimewiring/fulltrace/aggregatecaps T019/T021 UNRUN. |
| T018 | Build/start owned test stack and validate DB/oracle / O,V | T007,T010,T011,T015 | P0 | BLOCKED | Sequential bounded build/start of owned test DB only; actual seed/migration/reset/grader adversarial tests pass against PostgreSQL; existing-service health unchanged, ports/limits checked; record results, preserve unrelated volumes. OwnedDB created healthy without host publication;9realPGtests+grant correction+productionbackend lifecycle passed, but final independent runtime test stopped beforeSQL atRAM<20GiB. Preserve actual earlier evidence,do not claim finalPASS. |
| T019 | Deterministic full-stack integration / O,V | T013,T014,T016,T017,T018 | P0 | WAITING | Integrate telemetry, run real MCP with scripted model and Python harness; exact 25,000-cent draft graded, wrong writes fail, reset restores seed hash, replay/concurrent duplicate create one row; timeout-after-commit retry safe. |
| T020 | Runtime security negative tests / V | T019 | P0 | WAITING | tests/security prove agent cannot access grader secrets/admin APIs, rejected caller/tenant/unauthorized calls cause zero writes, no model-controlled network/shell tools; host-network broad reach explicitly documented and local services unpublished. |
| T021 | Baseline observability/metrics verification / V | T019 | P0 | WAITING | tests/telemetry use known synthetic durations/counts to verify metric attribution, null unavailable tokens/energy, cost denominator and failure records; one complete correlated trace/summary per attempt; tracing failure is visible. |
| T022 | Live-call readiness review / O,R,V | T020,T021 | P0 | WAITING | Fresh T007 evidence, exact model digest/capability and residency rechecked, deterministic checks pass, no open P0/P1, candidate review complete, one-call monitoring/abort controls ready. |
| T023 | One live Qwen draft / O,V | T022 | P1 | WAITING | Real installed Qwen emits MCP tool calls and persisted invoice matches oracle; replay stable, before/during/after host measurements and trace saved; timeout/unsupported tool use fails honestly rather than substituting scripted success. |
| T024 | Extend to ten executable tools / D,M | T023 | P1 | WAITING | Add seven specified read-only tools from catalog below, project/timesheet migrations/seeds and authorization checks; all ten execute real seeded queries; three-tool invoice unchanged and every tool has success/invalid/denied tests. |
| T025 | Ten-tool full-context baseline / E,V | T024 | P1 | WAITING | Versioned development tasks with required-tool sets; held-out fixtures reserved unopened until frozen comparison; three serial development-only smoke attempts including invoice/project/timesheet reads produce complete grades/traces/reset hashes; report all outcomes with fixed model/budget. |
| T026 | Freeze retrieval comparison protocol / C,E | T025 | P0 | WAITING | Freeze splits, query construction, k, metadata/ACL filters, embedding/tokenizer/model versions, fusion, hierarchy, tie rules, catalogs, budgets and pilot procedure before held-out use; attempt-count selection rule fixed now, final counts registered at T039; explicit definitions below resolved into contract fixtures. |
| T027 | Selector interface and full-context adapter / A | T026 | P1 | WAITING | internal/retrieval API accepts query/history/catalog/principal/budget; returns authorized ordered tools, scores and cost trace; full-context exposes every authorized schema without truncation; common contract tests. |
| T028 | Frozen catalog/index builder / I | T026 | P1 | WAITING | catalog/ snapshots/index manifests hash schemas and embedding config; invalid schema fails, stale/missing index explicit, permissions never inferred from embeddings; index build limits and memory measured after fresh T007 admission. |
| T029 | Semantic top-k / A | T027,T028 | P1 | WAITING | internal/retrieval/semantic/ passes frozen ranking/tie/ACL tests; top-k schema IDs and embedding/query costs recorded; missing index fails per frozen policy; no silent full-context fallback. |
| T030 | Hybrid selector / A | T027,T028 | P1 | WAITING | internal/retrieval/hybrid/ enforces authorization/metadata before frozen keyword/vector fusion; deterministic ties, known ranking fixtures, denied-tool tests and all filtering/retrieval costs recorded. |
| T031 | Hierarchical selector / A | T027,T028 | P1 | WAITING | internal/retrieval/hierarchical/ selects frozen authorized domains then tools; all routing calls/tokens/latency charged inside same total budget; missing/wrong domain decisions observable; adversarial domain fixtures pass. |
| T032 | Cross-strategy fairness gate / V | T029,T030,T031 | P0 | WAITING | Equal principal/model/tasks/execution limits/DB start hashes; retrieved required-tool coverage and oracle metrics validated; unauthorized execution blocked at server for every strategy; protocol and dependency manifests immutable. |
| T033 | Catalog scaling and pilot / E,I | T032 | P1 | WAITING | Generate and validate 10/100/1000-tool catalogs; each exposed tool has a sandboxed executable implementation or explicitly typed safe mock; pilot checks context overflow, feasible run counts and host pressure without held-out tuning. |
| T039 | Final campaign preregistration / C,E | T033 | P0 | WAITING | Exclusive output `docs/benchmark/PREREGISTRATION.md`; before held-out access, publish immutable pilot-derived task/repetition counts, seeds, order, exclusions, model/catalog/index/config hashes and analysis plan; R verifies adherence to T026 selection rule; no test-set tuning. |
| T034 | Controlled benchmark campaign / O,E | T039 | P1 | WAITING | Frozen pilot-derived counts, four strategies, counterbalanced order, serial attempts, controlled state and fresh admission; retain all attempts including timeout/overflow; exact rerun manifest and immutable raw artifacts. |
| T035 | Reliability injection harness / I,V | T032 | P2 | WAITING | tests/reliability scoped faults for index/server outage, timeouts, duplicates, schema changes and telemetry loss; deterministic expected failure/recovery labels; no host/global fault injection; shared budgets enforced. |
| T036 | Bounded concurrency/contention experiments / O,V | T034,T035 | P2 | WAITING | Separate fresh capacity review defines max concurrency/workload; run isolation and same-key tests show zero cross-run contamination; pressure abort verified using owned workloads only, no interference deliberately applied to homelab apps. |
| T037 | Reproducible analysis / E | T034,T035,T036 | P1 | WAITING | analysis/ recomputes success, retrieval, latency, token/compute and reliability tables from immutable attempts; paired comparisons with denominators/uncertainty, failures and context limits retained; missing energy/cost explicitly unavailable. |
| T038 | Final report and reproduction gate / C,O | T037 | P1 | WAITING | reports/ documents measured tradeoffs, failures, hardware/model/catalog hashes, commands and limitations; independent V reruns analysis and one small allowed trial, R verifies claims against artifacts; no unsupported winner claim. |

## Shared assumptions for this wave

[WAVE1_CONTRACT_ASSUMPTIONS.md](WAVE1_CONTRACT_ASSUMPTIONS.md) is the approved
planning baseline for T003–T005. It is not a substitute for T006 machine-readable
contracts. T006 is READY after these documentation prerequisites pass, but is not DONE
until its machine-readable schemas, independent review and validation pass.
READY does not authorize dispatch; the next wave still needs user approval.

## Catalog contract to freeze at T006

Smoke tools: `billing_list_customers`, `billing_list_items`,
`billing_create_draft_invoice`. Proposed baseline adds seven read-only tools:
`billing_get_customer`, `billing_list_projects`, `billing_get_project`,
`billing_list_timesheets`, `billing_get_timesheet`, `billing_list_invoices`,
`billing_get_invoice`. No sending, payment or production API capability. T006
specifies trusted principal/run-context transport, DB/schema mapping and evaluator
control rights (never model-chosen), as well as pagination/result caps, IDs/date filters and exact error schemas before
any implementation. T024 may not invent these during coding. Permission fixture
includes billing-reader (reads only) and billing-drafter (reads + create draft);
server independently enforces every call using a trusted synthetic principal.

## Acceptance definitions shared by nodes

- Invoice smoke oracle: CUST-001, 2026-11-07 invoice, 2026-11-21 due, USD,
  SVC-CONSULT quantity 2 × 12,500 cents, total 25,000 cents, tax zero, status draft,
  one invoice and no unrelated writes; final answer identifies persisted ID.
- Controlled reset: a dedicated per-run database or schema inside MCPBench's own
  PostgreSQL, canonical seed fingerprint before execution and after cleanup;
  infrastructure credentials only in evaluator/control plane. Compare all relevant
  tables and detect unexpected records. Save evidence before cleanup even on failure.
- Metrics: recall = required authorized tool IDs exposed / required IDs; precision
  = relevant authorized IDs exposed / exposed IDs, with null for zero denominator;
  required sets fixed per task and retrieval step at T004/T026. Unsupported
  alternative valid plans need fixture annotation before held-out scoring.
  Report denied selection attempts separately from executed unauthorized calls
  (the latter must be zero). Attribute errors by observable stage, allow multiple
  labels, and mark reasoning attribution uncertain when evidence cannot separate it.
- Cost: observed CPU/container memory, model durations and tokens per successful
  task; total attempt compute divided by successes, null if zero. Local inference
  dollar/energy estimates require declared measurements/rates; never invent prices.
- Comparable budgets include routing, retrieval, embeddings, model turns, retries
  and tools. Separate one-time index build from per-task cost, never hide it.
  Overflow/timeouts are outcomes, not grounds for silent catalog truncation.
- No task completion by narrative: R reports no open P0/P1, V supplies observed
  PASS/FAIL/UNRUN evidence for every criterion, O records handoff and state update.
  Checks requiring T007 remain UNRUN until admitted. Read-only planning review
  does not imply code or live-model validation.

## Accepted documentation wave — 2026-11-07

T003/T004/T005 are DONE under the explicit documentation-only exception: source
candidates frozen at state/candidates/wave1-frozen-v2.json, independent reviewer
APPROVE and tester PASS at state/reviews/wave1-reviewer-v2.md and
state/reviews/wave1-tester-v2.md. Cross-document late-write lifecycle finding was
fixed before acceptance. No Git commit/merge or runtime verification is claimed.
T006 is READY but unstarted/unapproved; T001/T002 remain BLOCKED. All other nodes
remain WAITING; no runtime or application implementation is approved.

## Permission refresh wave — 2026-11-07

Current facts: see NODE1_AUDIT.md. T002 is DONE with normal Git baseline
e0ce746 and independent review/test; T001 remains BLOCKED on actual model-storage filesystem verification,
not Docker/Ollama sockets. Reopen T003–T005 only for bounded documentation refresh
against these observations; their earlier v2 approval remains historical evidence.
Use separate Git worktrees and exclusive files. T006 waits for refreshed candidates;
no application, Docker mutation or live Ollama call is authorized. Metadata tool
capabilities do not complete T040. Python evaluator, Go server/agent, four strategies
and JSONL-only v1 remain unchanged. OpenTelemetry and Jaeger remain v2.

## Permission-refresh acceptance

T002 and refreshed T003–T005 are DONE: independent access-refresh reviewer APPROVE
and tester PASS in state/reviews/access-refresh-reviewer.md and
state/reviews/access-refresh-tester.md. Three clean exclusive task commits were
cherry-picked into main; reviewed source hashes match. No P0/P1 documentation
finding remains. T001 is still BLOCKED solely on service-account model-storage
target/filesystem verification. T006 is READY for the next contract wave, not DONE.
T007, T040, T008 and all application/runtime tasks remain WAITING.

## Active v1 goal authorization — 2026-11-07

The user explicitly authorized autonomous execution of eligible DAG tasks with
independent review/testing and integration. Routine transitions, including T040
after T007, no longer need repeated per-wave approval. Existing resource/security
gates remain binding; security-sensitive changes, architecture changes, unresolved
P0/P1 and genuine blockers require stopping rather than bypass. OpenTelemetry,
Jaeger and dashboard are outside v1. T006 is now IMPLEMENTING in an isolated
worktree; T001 revalidation still fails service-account model-path reads/sudo.
No runtime gate is waived and no loaded-model inference is performed.

## Contract milestone accepted

T006 DONE at reviewed candidate32bafe0, integrated normally; reviewer APPROVE and
tester PASS in state/reviews/T006-reviewer-v3.md and T006-tester-v3.md. Main-checkout
32 contract tests and Catalog/Task CLI validation PASS; source hashes match. T009
is now READY independently of runtime access. T007/T040/T008 still wait on T001
actual model-store evidence plus their other prerequisites. Runtime proofs UNRUN.

## Fixture milestone accepted and admission impasse

T009 DONE at reviewed f6b196e, merged normally. Reviewer APPROVE/tester PASS in
state/reviews/T009-reviewer-v1.md and T009-tester-v1.md; 46 combined tests and
corpus CLI PASS in main. All11 source hashes match approved candidate. No static
P0/P1 remains. Recalculated DAG has no READY tasks: T001 model-store filesystem
evidence remains BLOCKED, T007/T040/T008 and all downstream work are WAITING.
Fresh20:00 host checks still have working Git/Docker/Ollama and sudo authentication
required for private model-path readlink/df. No security/resource gate is waived.
