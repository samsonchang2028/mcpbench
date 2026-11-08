# Evaluation plan

Current milestone: T006 machine-readable contracts and local validation now PASS
independent review/testing; see contracts/README.md and state/handoffs/T006.md.
The active v1 goal authorizes routine admitted DAG execution. Earlier documentation-
only/per-wave approval wording below is historical; runtime proof remains gated.

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

## Readiness evidence — 2026-11-07 permission refresh

The refreshed [Node 1 audit](NODE1_AUDIT.md) verifies normal Git writes, read-only
Docker inspection and native Ollama metadata connectivity. Installed model
`qwen3.5:9b` is Q4_K_M, served by Ollama 0.40.13, with digest
`56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90`.
The API advertises tool support, and `/api/ps` returned no loaded models at that
inspection. These observations establish installed identity and sampled residency,
not valid tool calls, future exclusive availability or a completed T040 probe.

About 25 GiB available RAM and the retained 60-second zero-swap sample satisfy
only numeric observations. As of the audit, T001 remains blocked on verifying the
actual protected model-storage target/filesystem; T007 admission is incomplete.
The existing NVIDIA driver/library mismatch and unhealthy Immich ML container
are baseline constraints, not evaluation failures produced by MCPBench. Preserve
those services, record their baseline and recheck for regressions before any trial.
No GPU acceleration is established. T006 machine-readable contracts and both
live gates remain future work; no application or inference ran in this refresh.

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

Partial task projection, documenting selected values of a future fixture. This
example is not a complete valid task: permitted tools, expected state, final-answer
rule and budgets are intentionally omitted and remain required by the table above:

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

After agent execution access is revoked and every already-authorized operation
is settled (completed or rolled back with no possible later commit), the evaluator
takes the immutable **agent-only settled snapshot** of all run-owned application
tables using its grader role. Process exit alone does not prove settlement.
Evaluate this original state independently of model prose, MCP responses or later
verifier calls. For the smoke fixture assert:

- Exactly one new invoice: CUST-001, USD, `draft`, invoice date 2026-11-07,
  due 2026-11-21, tax zero, subtotal/total 25,000 integer cents.
- Exactly one new line: SVC-CONSULT, integer quantity 2, unit price 12,500 cents,
  linked to that invoice with correct canonical customer/item references.
- Existing customers/items and unrelated rows unchanged. Only the declared header,
  line and matching idempotency record may be added. No sent/paid state, payment
  or outbound accounting action exists.
- Structured final answer contains the persisted `invoice_id`; prose cannot
  override the DB verdict.

Replay is a separate post-agent verification phase, permitted only after the
original agent-only oracle and answer pass. It must never create a missing invoice,
repair a failed attempt or replace original correctness evidence. Same-key/same-
payload replay must return the original ID without mutation; changed payload must
conflict without mutation. The final settled snapshot must equal the agent-only
application state. Verification failure fails the run gate even if the original
invoice was correct.

Read-only project/timesheet tasks use an explicit non-invoice applicability path.
After acknowledged agent revocation/settlement, grade the original answer's record
IDs against the exact declared set and prove application state unchanged. No
verifier capability or invoice call is issued; replay and verifier-settlement
verdicts are null with a typed read-only/not-applicable reason, and verifier calls
are zero. The registry remains sealed while a final unchanged-state snapshot and
safe scoped cleanup complete. The same post-agent 30-second bound applies. This
does not relax the draft-invoice smoke's two-call/two-fence verification gate.

A controlled comparison may contain a failed agent task: wrong answers, invalid
calls and model timeouts remain measured failures when setup, settlement, evidence
and cleanup are complete. Operational uncertainty, quarantine, failed verification
or incomplete evidence cannot be labeled comparison-valid. Recovered agent/tool
errors are retained without automatically invalidating a later correct task.

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
4. Execute one agent under fixed budgets. On result/deadline, preserve output,
   events and exit status; stop agent execution, revoke its execution capability
   and prevent new calls. An uncertain write outcome is not assumed rolled back.
5. Within the bounded settlement budget, prove every already-authorized operation
   completed or rolled back and cannot later commit. T006 defines the actual
   fence/drain protocol. If this cannot be established, record `settlement_unknown`,
   fail the smoke gate, mark comparison invalid and quarantine the run without
   reset/reuse while writes may still be active. A diagnostic snapshot cannot PASS.
6. Save the immutable agent-only settled snapshot and grade original DB/answer
   assertions before any verifier call. Preserve failed original attempts exactly;
   no replay may create or fix their invoice. Only when original DB/answer pass,
   use a separate trusted verifier capability constrained to this run/request for
   at most two calls: same-key/same-payload replay and changed-payload conflict.
   The agent never sees this capability and its own access remains revoked.
7. Revoke verifier access and settle/drain again before taking the final settled
   snapshot. Compare it to agent-only application state, asserting same invoice ID
   and no extra/changed records. Late mutation or unknown settlement fails run
   validation without overwriting original correctness evidence. If verification
   is skipped because original assertions failed, record the skip and still prove
   agent capability revocation/settlement before cleanup.
8. Persist both snapshots, assertions, settlement/revocation evidence, events,
   output and summary before cleanup. Only with all execution/verifier access
   revoked and writes known settled, reset the run-owned DB/schema to pinned seed
   and verify its fingerprint. Failed cleanup preserves evidence and quarantines
   the run. Unknown active writes prohibit reset/reuse; never clean shared volumes.

Fingerprinting sorts declared tables by stable keys, canonically serializes fields
and rows, and hashes migration/fixture versions plus seed records. It detects
missing/extra/changed seed rows. Agent-only and final settled snapshots separately
preserve dynamic rows; fingerprints do not replace explicit oracle assertions. Failed cleanup
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
results or malformed/oversized output fail the result contract; record failure
and follow revocation/settlement before an authoritative snapshot or safe cleanup.
Unknown active writes require quarantine instead.

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
{"schema_version":1,"run_id":"run-example-001","attempt_id":"attempt-example-001","event_id":"agent-0007","source":"agent","sequence":7,"timestamp":"2026-11-07T23:00:00Z","event_type":"tool.completed","phase":"execution","status":"ok","call_id":"call-002","elapsed_ms":1250,"data":{"tool_id":"billing_create_draft_invoice","duration_ms":18,"invoice_id":"INV-EXAMPLE-001","tool_result":{"tool_id":"billing_create_draft_invoice","is_error":false,"result":{"invoice":{"invoice_id":"INV-EXAMPLE-001","customer_id":"CUST-001","invoice_date":"2026-11-07","due_date":"2026-11-21","currency":"USD","status":"draft","subtotal_cents":25000,"tax_cents":0,"total_cents":25000,"created_at":"2026-11-07T23:00:00Z"},"lines":[{"line_id":"LINE-EXAMPLE-001","invoice_id":"INV-EXAMPLE-001","item_id":"SVC-CONSULT","quantity":2,"unit_price_cents":12500,"line_total_cents":25000,"line_number":1}]}}}}
```

Retain authorized catalog IDs/schema hash and ordered exposed IDs at each selection
step, sanitized relevant tool arguments/results, prompt/hash, model/settings,
retries and failures. Synthetic content only; exclude auth headers, passwords and
environment dumps, including secrets embedded in exception messages.

Evaluator-owned `artifacts/runs/<run_id>/` stores manifest, version hashes,
before, agent-only settled and final settled snapshots, seed fingerprints, JSONL
events, agent result/exit record, capability revocation/settlement evidence, original
assertions, separate verification assertions, cleanup record and summary. Agent
sees dedicated request/output paths only. Final artifact manifest records SHA-256 hashes and completeness flags.
Finalized attempts are immutable; reruns make new attempts. Inference may vary:
“deterministic artifacts” means the same stored evidence plus frozen grader yields
the same assertions/metrics, without rerunning the model.

## Results, attribution and validity

Evaluator summary contains version, run/attempt/task IDs, version hashes,
`agent_status`, `agent_settlement_pass`, `verifier_settlement_pass`,
`db_oracle_pass`, `answer_pass`, `replay_pass` when checked, `cleanup_pass`,
`artifact_complete`, `comparison_valid`, `task_success`, failure records, original
and verification assertions and metrics. Unchecked replay or skipped verifier
settlement is null with a reason, not false. Unknown agent settlement makes its
authoritative DB verdict null; a diagnostic read cannot assert PASS.
Task success requires the original settled DB/answer assertions, completion within
the agent budget and no unsafe/unauthorized execution. Verifier activity cannot
change that original verdict or rescue a timeout. Replay, settlement, cleanup or
artifact failure makes overall run status failed; report original task correctness
and comparison validity separately. The smoke gate requires both settlement fences,
original correctness, replay, cleanup and artifact completeness to pass. Unknown
settlement makes comparison invalid and requires quarantine without risky reset.

| Stage | Observable labels and attribution |
| --- | --- |
| Admission/prepare | `admission_blocked`, `fixture_invalid`, `prepare_failed`, `reset_failed`; no agent execution |
| Retrieval | `required_tool_missing`, `retrieval_unavailable`, `index_stale`, `context_overflow`; compare exposed IDs to frozen annotations |
| Agent/model | `model_unsupported`, `unknown_tool`, `invalid_arguments`, `unauthorized_attempt`, `no_result`, `answer_invalid`, `model_timeout`, `budget_exhausted` |
| MCP/execution | `protocol_error`, `authorization_denied`, `tool_error`, `db_error`, `tool_timeout`, `idempotency_conflict` |
| Grading/operations | `state_incorrect`, `unexpected_write`, `grader_error`, `settlement_unknown`, `verification_failed`, `cleanup_failed`, `resource_abort`, `interrupted`, `artifact_incomplete` |

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
| Latency | Launcher monotonic task duration from agent start to output/termination; separately record prepare, discovery, retrieval, model, tools, original grading, post-agent settlement/verification, cleanup and full lifecycle; do not sum overlapping intervals |
| Compute per success | Total measured lifecycle CPU time including settlement/verification / successful tasks; null for zero successes or missing measurements; sampled peak memory and model durations reported separately |
| Cost/energy | Null without measured energy or declared defensible rates; no invented local inference price or energy inferred from tokens |
| Recovery | Agent attempts/outcome inside original retry/deadline budget; separately bounded verifier replay never repairs original state or extends agent budget |

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

Post-agent settlement/verification has a separate maximum of **30 seconds total**,
**5 seconds per settlement, verifier or DB operation**, **two verifier calls** and
**no verifier retries**. The total includes both settlement fences and original/
final snapshot/grading operations; hitting any bound yields failed verification
and unknown settlement where applicable, never an unbounded drain. These limits
are outside the 300-second agent deadline and cannot extend it or rescue timeout.
Record/charge all post-agent latency and compute in full lifecycle measurements,
identically across strategies. Agent selection/call metrics exclude verifier calls
but expose their separate counts/costs; no verifier model tokens are attributed to
agent reasoning. T006 freezes exact fencing/capability protocol and failure fields.

## Validation ladder and later comparisons

T004 is documentation only. Later gates require actual observed evidence:

| Gate | Required evidence |
| --- | --- |
| T006 contracts | Machine-readable schemas validate examples/negative cases and align launcher, agent, server identity/routing; secrets excluded |
| T010 oracle/reset | Wrong snapshots fail; failed reset prevents execution; late-commit/unknown-settlement cases quarantine without reset; replay cannot create a missing invoice |
| T018 DB integration | Actual PostgreSQL migrations, seed twice, isolation, reset fingerprints and adversarial oracle cases pass |
| T019–T021 deterministic slice | Real MCP, scripted model, Python lifecycle and JSONL agree; both revocation/settlement fences, non-repair replay, duplicate/retry safety, security and known-metric cases pass |
| T040 early probe | Successful admission plus active-goal authorization; real Ollama returns valid `probe_echo` call; metadata/scripted output insufficient, no billing writes |
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
