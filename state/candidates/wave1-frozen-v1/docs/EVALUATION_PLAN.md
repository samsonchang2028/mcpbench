# Evaluation plan

Status: T004 documentation candidate. These are proposed v1 behavioral contracts,
not evidence of working software. The shared baseline is
[WAVE1_CONTRACT_ASSUMPTIONS.md](WAVE1_CONTRACT_ASSUMPTIONS.md); T006 must convert
these definitions into machine-readable contracts and validate examples. No
application, Docker operation or live Ollama call is authorized by this document.

## Scope and ownership

Preserve the research question: how full context, semantic top-k, hybrid and
hierarchical MCP retrieval affect success, latency, tokens, cost and reliability
as catalogs scale. Use comparable permissions, model settings, tasks and total
budgets, without assuming a superior strategy.

V1 first proves the three-tool draft-invoice slice with full context, then a
ten-tool executable baseline. Python owns prepare/reset, independent grading,
artifact assembly and summaries. A separate Go agent owns MCP discovery,
Ollama conversations and validated dispatch; the Go MCP server enforces billing
and authorization. V1 uses structured JSONL, run IDs and deterministic artifacts.
OpenTelemetry, Jaeger and collectors are deferred to v2.

The trusted host launcher sequences Python prepare → Go agent execute → Python
grade/reset. It handles fixed process transport/lifecycle, never a model tool.
The evaluator container reaches benchmark PostgreSQL on its private network;
the separate agent container reaches native Ollama and MCP through fixed loopback
endpoints. Neither container mounts the Docker socket or runs privileged. Expected
states, DB credentials and grader/control files never enter the agent's mounts,
environment, request, prompt or logs. The launcher supplies allowlisted arguments,
sanitized environment and trusted run-scoped synthetic auth/routing metadata.

## Fixture and task contract

All contract objects carry `schema_version` (initial value `1`). Unknown major
versions, invalid fields, inconsistent IDs or missing mandatory fields are
rejected before execution. T006 fixes machine-level types, bounds and errors.

| Object | Required content and invariants |
| --- | --- |
| Fixture manifest | `fixture_id`, `fixture_version`, `seed_hash`, migration version, fictional tenant, canonical seed records and expected-state rules; evaluator-only storage |
| Task definition | `task_id`, `task_version`, `fixture_id`, prompt, synthetic principal ID, permitted tools, required/relevant tool annotations, expected state, final-answer rule, budgets and development/held-out split |
| Execution manifest | `run_id`, `attempt_id`, task/fixture/catalog/config hashes, strategy, model tag/digest, principal ID, budgets and exact component/image/dependency versions or explicit unavailable values |

`run_id` identifies one isolated attempt; `attempt_id` is unique and retained.
Transport retries remain inside that run/attempt and budgets. An independent
trial gets new IDs, idempotency key and isolated DB/schema. A replay subcheck uses
the original key and existing invoice; it is not another successful trial.

Example task values, documenting a future fixture:

```json
{
  "schema_version": 1,
  "task_id": "draft-invoice-001",
  "task_version": "1",
  "fixture_id": "billing-smoke-001",
  "split": "development",
  "principal_id": "billing-drafter",
  "prompt": "Create a draft invoice for customer CUST-001 for two hours of SVC-CONSULT, dated 2026-11-07, due 2026-11-21. Do not send it.",
  "required_tool_ids": ["billing_create_draft_invoice"],
  "relevant_tool_ids": ["billing_list_customers", "billing_list_items", "billing_create_draft_invoice"]
}
```

The prompt gives stable IDs, so only creation is required for a valid minimal
plan; listing tools are relevant but optional. Name-lookup tasks must annotate
required read tools. Multiple valid plans use a predeclared list of acceptable
required sets and a frozen scoring rule; never add a plan after observing a
held-out result. This first fixture has exactly the required set shown above.

## Independent database oracle

After the agent exits or is terminated, the evaluator takes a consistent snapshot
of all run-owned application tables using its grader role. Evaluate DB facts
independently of model prose or MCP responses. For the smoke fixture assert:

- Exactly one new invoice: CUST-001, USD, `draft`, invoice date 2026-11-07,
  due 2026-11-21, tax zero, subtotal/total 25,000 integer cents.
- Exactly one new line: SVC-CONSULT, integer quantity 2, unit price 12,500 cents,
  linked to that invoice with correct canonical customer/item references.
- Existing customers/items and unrelated rows unchanged. Only the declared header,
  line and matching idempotency record may be added. No sent/paid state, payment
  or outbound accounting action exists.
- Structured final answer contains the persisted `invoice_id`; prose cannot
  override the DB verdict.
- Same-key/same-payload replay returns that ID without another row; changed payload
  with the same key is rejected without mutation.

Expected state uses stable business keys and explicit totals. Generated IDs and
timestamps may vary but must satisfy declared reference/type/date constraints.
Never take model-generated totals as expected values. Include the idempotency
record in expected changes so a correct safety write is not flagged as unrelated.

Before billing code, test the grader with wrong customer, price, total, status,
dates, extra lines/rows and unchanged/no-write snapshots. Actual PostgreSQL reset
and oracle integration evidence belongs to T018; snapshot unit tests do not prove
DB correctness.

## Controlled lifecycle and reset

1. Validate versions, runtime approval and fresh admission evidence. Allocate a
   run-owned DB/schema through trusted mapping; model text cannot select it or
   supply SQL/identifiers to cleanup.
2. Apply pinned migrations/seed. Verify canonical seed fingerprint before starting
   the agent. Failed prepare/reset records failure and prevents execution.
3. Save before snapshot/hash and sanitized request. Expose only agent request and
   dedicated event/result paths, excluding expected states and parent artifact
   directories. Trusted idempotency metadata is not model-editable tool input.
4. Execute one agent under fixed budgets. Record exit status even on crash,
   timeout or malformed/no result. Retry only within policy; unknown write outcome
   preserves the same idempotency key.
5. Snapshot and grade DB state. Persist events, bounded agent output, assertions
   and summary before cleanup, including every failure.
6. Reset only the run-owned DB/schema to pinned seed and verify its fingerprint.
   Save cleanup outcome. Failed cleanup preserves evidence and quarantines the
   run; never clean shared/homelab volumes.

Fingerprinting sorts declared tables by stable keys, canonically serializes fields
and rows, and hashes migration/fixture versions plus seed records. It detects
missing/extra/changed seed rows. Post-run snapshots separately preserve dynamic
rows; fingerprints do not replace explicit oracle assertions. Failed cleanup
leaves task-correctness evidence intact but makes overall run status failed and
the attempt invalid for a controlled comparison.

## Launcher and agent request/result boundary

Use bounded versioned JSON via launcher-controlled run files or stdin/stdout;
T006 freezes the exact transport with equivalent validation. Requests contain
schema version, run/attempt/task IDs, prompt, strategy/catalog identity, principal
identifier and budgets. Endpoint/auth configuration comes from trusted launcher
allowlists, never model output. No grader expectations or DB credentials appear.

Agent result contains version, matching run/attempt IDs, completion status,
structured `final_answer` (`invoice_id` if a draft is claimed), call counts and
optional diagnostics. Claimed success is advisory. Invalid IDs/version, duplicate
results or malformed/oversized output fail the result contract; snapshot, record
failure and attempt cleanup anyway.

Launcher records process start/end, exit code/termination reason and complete-result
delivery. Stdout reserved for JSON result transport has no extra logs; events use
a separate stream/file. Final files publish atomically, never while partial.
Event lines and request/result documents each have a 1 MiB ceiling; total smoke
artifacts cap at 100 MiB. Cap exhaustion/truncation is `artifact_incomplete`, not
silent success. T006 fixes finer field/array/string bounds within these ceilings.

## Structured JSONL and deterministic artifacts

Each line is a JSON object with mandatory `schema_version`, `run_id`, `attempt_id`,
`event_id`, `source` (`launcher`, `evaluator`, `agent`, `mcp`), source-local increasing
`sequence`, UTC `timestamp`, `event_type`, `phase`, `status`, source-local monotonic
`elapsed_ms` and bounded typed `data`. Use `call_id` and parent call ID when
applicable. Every start has completion/error or an explicit interrupted marker.
Never compare monotonic clock origins across producers: the launcher measures
end-to-end with its own clock; each producer reports local durations.

Example event:

```json
{"schema_version":1,"run_id":"run-example-001","attempt_id":"attempt-example-001","event_id":"agent-0007","source":"agent","sequence":7,"timestamp":"2026-11-07T23:00:00Z","event_type":"tool.completed","phase":"execution","status":"ok","call_id":"call-002","elapsed_ms":1250,"data":{"tool_id":"billing_create_draft_invoice","duration_ms":18,"invoice_id":"INV-EXAMPLE-001"}}
```

Retain authorized catalog IDs/schema hash and ordered exposed IDs at each selection
step, sanitized relevant tool arguments/results, prompt/hash, model/settings,
retries and failures. Synthetic content only; exclude auth headers, passwords and
environment dumps, including secrets embedded in exception messages.

Evaluator-owned `artifacts/runs/<run_id>/` stores manifest, version hashes,
before/after snapshots, seed fingerprints, JSONL events, agent result/exit record,
assertions, cleanup record and summary. Agent sees dedicated request/output paths
only. Final artifact manifest records SHA-256 hashes and completeness flags.
Finalized attempts are immutable; reruns make new attempts. Inference may vary:
“deterministic artifacts” means the same stored evidence plus frozen grader yields
the same assertions/metrics, without rerunning the model.

## Results, attribution and validity

Evaluator summary contains version, run/attempt/task IDs, version hashes,
`agent_status`, `db_oracle_pass`, `answer_pass`, `replay_pass` when checked,
`cleanup_pass`, `artifact_complete`, `comparison_valid`, `task_success`, failure
records, assertions and metrics. Unchecked replay is null, not false.
Task success requires DB/answer assertions and no unsafe/unauthorized execution.
Required replay, cleanup or artifact failure makes overall run status failed;
report task correctness and comparison validity separately. The smoke gate requires
all checks, including replay, cleanup and artifact completeness, to pass.

| Stage | Observable labels and attribution |
| --- | --- |
| Admission/prepare | `admission_blocked`, `fixture_invalid`, `prepare_failed`, `reset_failed`; no agent execution |
| Retrieval | `required_tool_missing`, `retrieval_unavailable`, `index_stale`, `context_overflow`; compare exposed IDs to frozen annotations |
| Agent/model | `model_unsupported`, `unknown_tool`, `invalid_arguments`, `unauthorized_attempt`, `no_result`, `answer_invalid`, `model_timeout`, `budget_exhausted` |
| MCP/execution | `protocol_error`, `authorization_denied`, `tool_error`, `db_error`, `tool_timeout`, `idempotency_conflict` |
| Grading/operations | `state_incorrect`, `unexpected_write`, `grader_error`, `cleanup_failed`, `resource_abort`, `interrupted`, `artifact_incomplete` |

Keep every observed failure with stage, call ID and evidence. Missing tools followed
by wrong calls may get retrieval and agent labels. Reasoning attribution is marked
uncertain unless exposed schemas, execution and task evidence isolate it. Denied
selection attempts and actual unauthorized execution are separate; the latter must
be zero. Missing instrumentation makes attribution unknown, not retrieval failure.

## Metrics and budgets

| Metric | Definition / missing-data rule |
| --- | --- |
| Required-tool recall | At each selection step, required authorized IDs exposed / required authorized IDs; null for empty required set |
| Retrieval precision | Relevant authorized IDs exposed / exposed IDs; null for zero exposed; unauthorized IDs separately counted |
| Task success rate | Successful tasks / all attempted tasks, retaining agent failures; separately report admission-blocked requests and invalid-comparison attempts with every denominator |
| Tool errors | Counts/rates for unknown selections, invalid arguments, authorization attempts/denials, execution failures and wrong states; count retries |
| Tokens | Sum reported prompt/output counts across model/routing calls and retries; missing component makes total null, with known subtotal retained; estimates labeled separately |
| Latency | Launcher monotonic task duration from agent start to output/termination; separately record prepare, discovery, retrieval, model, tools, grading, cleanup and full lifecycle; do not sum overlapping intervals |
| Compute per success | Total measured attempt CPU time / successful tasks; null for zero successes or missing measurements; sampled peak memory and model durations reported separately |
| Cost/energy | Null without measured energy or declared defensible rates; no invented local inference price or energy inferred from tokens |
| Recovery | Attempts/outcome inside original retry/deadline budget, committed state after timeout and idempotent replay |

The first smoke exposes all three authorized tools in one selection step:
precision 3/3; minimal required-tool recall 1/1. Full context has zero search/index
latency, with discovery/schema preparation measured separately. Executed-call
correctness is not retrieval precision.

Total budgets include routing, embedding, model calls, tools and retries: supported
context 4096, output cap 512, temperature 0, at most 8 model turns and 12 tool calls,
5-second DB/tool deadlines, 120-second model deadline and 300-second task deadline.
One transient retry maximum inside those totals; record supported seed/thinking/
keep-alive settings without global Ollama changes. Context overflow is an outcome,
never permission to silently truncate schemas. Admission/abort policy remains in
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## Validation ladder and later comparisons

T004 is documentation only. Later gates require actual observed evidence:

| Gate | Required evidence |
| --- | --- |
| T006 contracts | Machine-readable schemas validate examples/negative cases and align launcher, agent, server identity/routing; secrets excluded |
| T010 oracle/reset | Wrong snapshots fail; failed reset prevents execution; only correct invoice passes |
| T018 DB integration | Actual PostgreSQL migrations, seed twice, isolation, reset fingerprints and adversarial oracle cases pass |
| T019–T021 deterministic slice | Real MCP, scripted model, Python lifecycle and JSONL agree; duplicate/retry safety, security and known-metric cases pass |
| T040 early probe | Admission plus separate approval; real Ollama returns valid `probe_echo` call; metadata/scripted output insufficient, no billing writes |
| T022–T023 live invoice | Fresh readiness, monitored real Qwen and full DB/answer/replay/cleanup/artifact smoke gate pass |
| T025 baseline | Ten executable tools, development-only task attempts, all outcomes saved |

Preserve all four strategies: full context exposes authorized schemas; semantic
top-k ranks task/query embeddings; hybrid combines authorization/metadata filters,
keyword and vector ranking; hierarchical chooses domains before individual tools.
Every strategy shares server permissions and total budgets. Charge routing calls,
tokens, latency and embedding cost; report indexing/update time/memory separately.

T026 freezes splits, query/history policy, relevance annotations, k, embedding and
keyword models/tokenizers, fusion, category tree, ties, catalogs, budgets, pilot
procedure and attempt-count selection rule using development data. After T033's
pilot, T039 registers final counts, seeds, counterbalanced order, exclusions and
analysis plan before held-out access, exclusively in
`docs/benchmark/PREREGISTRATION.md`. T034 then executes that frozen campaign.

Run serially initially with equal seed/model/config/permission hashes. Record
cold/warm loading without forced unloads, interference and interruptions. Keep
timeout/overflow/failure outcomes and report paired comparisons, denominators and
uncertainty. A smoke task establishes neither a winner nor deterministic inference.
