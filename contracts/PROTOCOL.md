# V1 component and terminal-state protocol

Normative T006 contract candidate. It specifies the approved design's missing
wire details; it does not deploy privileges or start services. Runtime acceptance
still needs the DAG's resource/security gates and independent database tests.

## Versions, wire limits and identities

All transport objects use `schema_version: 1`, strict UTF-8 JSON, unique object
keys and the accompanying named schema plus semantic validator. Documents and
event lines are at most 1 MiB; one smoke run's artifacts are capped at 100 MiB.
Parsing rejects NaN/Infinity, excessive nesting, Unicode surrogates and malformed
JSON. Monetary values and quantities use integer lexical forms only, bounded by
9,007,199,254,740,991 for interoperable exact JSON integer arithmetic. Reject an
arithmetic result above that bound before committing. Observed timing/count data
can record a limit violation; it is not clipped to the requested budget.

`Identifier` is 1–64 lower-case ASCII letters/digits/hyphens, beginning with a
letter. Run, attempt, task, event, call and idempotency IDs use that type; existing
`run-example-001` and `attempt-example-001` examples remain valid. The controller
generates unique run/attempt IDs with unpredictable random suffixes; IDs never
grant access. Business IDs are bounded uppercase ASCII identifiers. Dates are
YYYY-MM-DD, UTC timestamps use a final Z and at most six fractional digits.

The registered application schema is `r_` plus the first 32 hexadecimal SHA-256
characters of the trusted ASCII run ID. Unique DB constraints on run ID and schema
name must reject collisions, never reuse another run. Only the controller creates
and records that binding; MCP obtains its target from the immutable registry row,
never an HTTP/model-supplied SQL identifier. Validate the registered identifier and
quote it using the database driver's identifier API; all values are parameters.

## Fixed launch and artifact boundary

Default transport is run-specific files. No shell command is constructed from a
request. The host launcher uses only the explicitly selected pinned image digests
from T008/T015 and these fixed entrypoint arguments:

| Child | Fixed command/arguments | Inputs and outputs |
| --- | --- | --- |
| Python evaluator | `python -m eval.runner prepare`, `settle-grade`, or `finalize` | Private control request/config; prepare creates sanitized agent input and private capability input; later phases seal, snapshot/grade and safely reset |
| Go execution agent | `/app/agent run --request /run/mcpbench/request.json --auth /run/secrets/auth.json --output /run/mcpbench/output` | `AgentRequest`, separate private `AuthInput`; writes `result.json` and `events.jsonl` |
| Trusted verifier | Same Go image, `/app/agent verify --request /run/mcpbench/request.json --auth /run/secrets/auth.json --output /run/mcpbench/output` | `VerificationRequest`, a distinct verifier `AuthInput`; performs only the two fixed MCP checks and no model call |

The Python evaluator is on the private benchmark DB network. It cannot launch a
container or call native Ollama; the host launcher transports only typed phase
decisions/results and owns lifecycle. `settle-grade` emits either a bounded verifier
request or an explicit skip/quarantine decision. `finalize` consumes the verifier
exit/result if any and applies the second fence and safe cleanup policy. Both use
the same absolute post-agent deadline; process startup/transport time is charged.
Exact evaluator CLI configuration is fixed trusted control-plane configuration,
not a model-supplied command or generic phase interpreter.

The agent/verifier use host networking, have no listener, run as UID/GID 1000 on
the verified Node 1 host, with all supplementary groups/capabilities dropped,
`no-new-privileges`, read-only root and bounded `/tmp`. A different host UID must
be represented in reviewed deployment configuration, not compensated by broad
file permissions or privileged mode. Matching the host file owner does not mount
its filesystem or grant its groups: no Docker socket, host PID namespace, other
host directories, evaluator secrets or parent artifact directory is visible.

The controller owns `artifacts/runs/<run_id>/` as mode 0700. Bind only the sanitized
request file to `/run/mcpbench/request.json` read-only, private mode-0600 auth file
to `/run/secrets/auth.json` read-only, and the child's own output directory to
`/run/mcpbench/output` writable. Agent and verifier outputs are separate. Never
mount their parent, oracle/expected-state files, snapshots or control configuration.
Create paths without following symlinks and reject symlink/path escapes, duplicate
IDs, preexisting result files or unexpected file types before launch. Write results
atomically via a same-directory temporary file, fsync and rename without replacing
another finalized attempt. Stdout is unused in file mode; stderr contains bounded
redacted categories only. JSONL events use their own file, not result transport.

Start the agent with a cleared environment and only `PATH=/usr/local/bin:/usr/bin:/bin`,
`LANG=C.UTF-8`, `TZ=UTC`, `HOME=/nonexistent`, `TMPDIR=/tmp`. Do not inherit proxy,
DB, cloud, model-service or credential environment variables. Fixed HTTP targets
are `http://127.0.0.1:11434/api/chat` and `http://127.0.0.1:18081/mcp`; disable proxy
inheritance and redirects. Endpoints are not model-visible tool arguments.
MCP accepts Host `127.0.0.1:18081`/`localhost:18081`; health checks inside the
container may use `127.0.0.1:8080`/`localhost:8080`. Reject unrecognized Host and
nonempty Origin except `http://127.0.0.1:18081` or `http://localhost:18081`.
Host/Origin are not authentication. No arbitrary URL/shell/file tool exists.

The evaluator's separate trusted configuration supplies fixed `PGHOST=db`,
`PGDATABASE=mcpbench` and mode-specific project role/PGPASSFILE paths; never put
these in `AgentRequest`, logs or fixtures. Its grading connection uses only the
read-only grader role, distinct from its controller connection. A trusted Python
image may implement both roles but this is logical/connection separation, not a
claim that two functions in the same process have OS isolation. The benchmark
agent never receives either credential. No child receives a Docker socket.

## Opaque capability, ACL and idempotency

The controller generates each capability from 32 cryptographically random bytes,
encoded as 64 lowercase hex characters. `AuthInput` is secret delivery, not a
loggable artifact. Only its SHA-256 digest is held in `RunMapping`; example digests
are inert test values. The caller sends `Authorization: Bearer <capability>` and
`X-MCPBench-Run-ID`, `X-MCPBench-Attempt-ID`, `X-MCPBench-Idempotency-Key` from
trusted input, never model arguments. Authenticate every MCP method, including
initialize/list/call, and compare token digests in constant time after bounded
lookup. Match run and attempt, phase, expiry, principal and allowed tools before
exposing data. A reader cannot create a draft; catalog filtering is supplementary.

Mint execution access immediately before agent launch, expiring no later than
its 300-second task deadline. Reject calls after expiry; a call admitted before
expiry still must finish or be fenced. Registry identity/routing fields are
immutable. Tokens/digests never appear in prompts, public events or task fixtures.
Revocation does not erase the historic receipt or application idempotency ledger.

Every draft write uses the controller's same run/request idempotency key, outside
model input. Its normalized hash is SHA-256 of canonical JSON
`{"tool_id":"billing_create_draft_invoice","arguments":<validated CreateDraftArgs>}`.
Keep line order, reject duplicate item IDs and unknown fields. The same key and
hash returns the saved draft; a changed valid payload conflicts. Header, ordered
lines and idempotency record commit atomically with canonical server prices, all
constraints and checked arithmetic. No partial successful state, send, payment,
tax or discount capability is permitted. Retry only an explicitly transient
transport/DB failure once inside the original task budget and keep the same key.
Domain/authorization/validation/conflict failures are not retried.
The only ToolError codes permitted to declare retryable are `db_error` and
`tool_timeout`, and only when the server identifies a transient transport/DB fault
(for example a serialization/deadlock abort or bounded transport timeout). Other
codes always carry retryable=false, including nested ToolResult errors. Permanent
DB constraint/configuration faults are not transient. Unknown write outcome does
not authorize reset; any permitted write retry keeps its existing key/payload and
remains inside the single original transient-retry budget. Verifier never retries.

## Concrete write settlement and least privilege

Use a project-private `bench_control.run_registry` row for each run, outside its
application schema. All tool calls, reads included, begin one ordinary DB
transaction, lock their registered row with `SELECT ... FOR SHARE`, and **then**
check the latest capability/phase/mapping in that locked row. Acquire no app-row
locks first. Hold this shared row lock through application reads/writes and the
transaction's positive commit or rollback acknowledgment. A detached/background
write, post-commit callback write, or pooled query outside this transaction is
forbidden. Do not retain an authorization decision across requests.

The evaluator's controller seals a run using `SELECT ... FOR UPDATE` on that
same row, with at most five seconds for the entire seal/commit operation. Once
the exclusive row lock is acquired, every earlier shared-locked call has ended;
new calls cannot pass the subsequent locked phase check. Atomically remove the
relevant token digest, change phase and increment generation, then commit. Issue
a positive `FenceReceipt` only after a timely positive COMMIT acknowledgment.
Use READ COMMITTED for tool/seal transactions so a waiter checks the updated row.
The agent is stopped before sealing; no successful revocation/settlement is claimed
while an exclusive seal is merely queued. A timeout, lost connection or uncertain
commit emits an unknown receipt and `settlement_unknown`, not a retry or PASS.

PostgreSQL row locks need UPDATE privilege even for a SELECT locking clause.
Freeze these roles for the new project DB only; this document executes no grants:

| Role | Allowed SQL capabilities | Forbidden capabilities |
| --- | --- | --- |
| `mcpbench_controller` | Own dedicated mcpbench DB's project control/run schemas; create/seed/reset registered run schemas; alter registry lifecycle/token columns | No cluster SUPERUSER/CREATEROLE/CREATEDB or access to another DB/service |
| `mcpbench_service` | SELECT necessary registry fields; UPDATE only inert non-key `lock_marker` column to satisfy row-lock privilege; USAGE + SELECT app tables; INSERT draft headers/lines/idempotency records | No UPDATE of capability/state/routing/expiry/generation fields, no schema/role/reset rights, no UPDATE/DELETE business rows |
| `mcpbench_grader` | Read-only transaction and SELECT registered run tables plus registry phase/generation needed for receipt checks | No row-lock UPDATE grant, writes, reset or controller credentials in its connection |

The service must not mutate `lock_marker`; it has no authorization/proof meaning.
Only a controller can modify phase/capability/routing columns. Never grant table-wide
UPDATE merely to make row locks work. Pin statement/lock deadlines inside the
five-second operation bound; app/transport cancellation is not settlement proof.
Use the dedicated project DB and scoped schema ownership: no global volume or
database cleanup. Actual grant and concurrent-transaction tests belong to T018–T020.

| Transition | Required observation and state |
| --- | --- |
| prepared → executing | Seed fingerprint verified; execution capability minted; generation 0 |
| executing → agent_sealed | Agent stopped, exclusive seal acknowledged; execution digest removed, generation 1; immutable agent-only snapshot under read-only repeatable-read transaction |
| agent_sealed → verifying | Original DB, answer and within-budget outcome all PASS; controller issues separate verifier digest/scope; generation stays 1 |
| verifying → final_sealed | At most two verifier calls; separate exclusive seal acknowledged, digest removed, generation 2; final settled snapshot |
| agent_sealed or final_sealed → cleaned | No valid execution/verifier capability and positive applicable fence; persisted evidence; scoped reset and canonical seed check |
| any uncertain operation | Preserve artifacts and quarantine outside run storage; no authoritative success snapshot, reset, reassignment or reuse |

A receipt records run/attempt, fence kind, generation, resulting phase, timely
acknowledgment, UTC commit time and zero remaining in-flight operations inferred
from the lock invariant. The grader verifies its run/generation and the sealed
registry state in the snapshot transaction. A syntactically valid receipt supplied
by an agent is never trusted: receipts are private controller-owned artifacts.
If sealing fails, quarantine may only be an external artifact because updating
the still-locked registry may itself be unsafe/unavailable. Do not fake a successful
DB quarantine write. Expiry alone does not prove existing writes have ended.

## Verification cannot repair original task failure

Save the settled agent-only snapshot and original answer/outcome before verifier
access exists. Only original PASS permits the distinct trusted verifier process.
The verifier's capability binds the existing invoice, original request hash and
same idempotency key. The server's verifier branch **only reads** the existing
idempotency record/invoice: identical payload returns that invoice; a valid changed
payload conflicts. Missing ledger/invoice returns `verification_not_replayable`;
it must never enter the ordinary INSERT/create branch. Wrong run/key/tool, expiry
or phase returns authorization denial with zero writes.

The second request changes only the first line's quantity by +1, or -1 if it was
already 1000. It stays schema-valid, uses the same key and must conflict. No other
customer/date/item/line can be substituted. After verifier revocation/settlement,
compare the full final app state with the original snapshot. Even a correct
original invoice cannot conceal a late verifier mutation or unknown final state.
Original failure skips verifier access and preserves its failed verdict; if the
first seal succeeded, safe cleanup may proceed from agent_sealed with a recorded
skip reason, without inventing a second verifier receipt.

All post-agent settlement, original/final snapshots/grading, transport and
verification share a 30-second absolute deadline, with at most five seconds per
operation, two verifier calls and zero verifier retries. This is outside the
300-second agent deadline and cannot extend/rescue it. Save latency/compute for
both phases separately and in full-lifecycle totals identically for all strategies.
Exceeded/unknown settlement quarantines; a failed reset never starts the next run.

### Read-only applicability and terminal truth table

Private RunMapping, control messages and EvaluationResult carry `workflow_kind`,
exactly Task.expected_state.kind. This field and oracle records never enter
AgentRequest. `ExpectedReadOnly.record_table` binds required_record_ids to one
seeded table and its relevant read tools; IDs absent from that fixture reject.
The read-only capability excludes create-draft and never enters verifying or
final_sealed. After the initial acknowledged seal, grade the unchanged-state oracle
and exact record-ID answer. Finalize saves the final unchanged snapshot under the
same generation-1 seal, preserves artifacts, then safely cleans up. No new verifier
capability or second fence is invented. Replay and verifier settlement are null
with `read_only` reasons; verifier calls are zero. The same total 30 seconds applies.

| Original / lifecycle evidence | Task success | Overall / comparison |
| --- | --- | --- |
| Settled, completed within-budget original; DB/answer assertions all pass | true | Draft additionally needs exactly two successful verifier checks, generation-2 fence and unchanged final state; read-only needs unchanged final state under generation 1; both need setup, artifacts, cleanup and post-agent budget |
| Wrong answer/state, invalid arguments or timeout; setup, settlement, final unchanged snapshot, artifacts and cleanup complete | false | failed; comparison may remain valid; invoice verifier is skipped with `original_failed` reasons and zero calls |
| Original passes but replay/final-state verification fails | true | failed; comparison invalid; original verdict is preserved |
| Unknown applicable settlement (including null), quarantine, failed cleanup or incomplete artifacts | Original correctness cannot be asserted without initial settlement | failed; comparison invalid; unknown settlement and quarantine forbid reset |
| Agent never started | false | blocked; comparison invalid; unperformed verdicts have `not_started` reasons |

Original assertions have unique names and include `db-oracle` and `answer`, whose
pass values exactly match their verdict fields. Original success requires all
original assertions true, setup success, completed status, budget success and zero
unauthorized execution. A terminal original-stage failure prevents original success.
Actual `metrics.unauthorized_executions > 0` is a safety incident independently of
original correctness: require terminal `unauthorized_execution`, quarantine, invalid
comparison and no cleanup/reset or next work. Retain the measured count. A denied
`unauthorized_attempt` with zero executions remains distinct and may recover.
Known task_latency_ms above 300000 requires agent_budget_pass=false; keep the
overrun and failed original verdict. A settled, otherwise complete timeout remains
an eligible failed comparison. Under-limit timing alone does not prove other budgets.
Failures explicitly distinguish terminal from recovered; only bounded reasoning/
tool errors can be recovered. Verification, settlement, cleanup, resource and
artifact failures cannot be relabeled recovered. Every null verdict has a closed,
field-specific reason code; arbitrary explanatory strings cannot bypass policy.

Invoice replay PASS requires exactly two calls and passing assertions named
`same-payload-replay`, `changed-payload-conflict`, `unchanged-state`; every retained
verification assertion must pass for a valid comparison. Skipped/read-only paths
retain only `unchanged-state`. Overall passed is equivalent to original success
plus a valid completed lifecycle/comparison; a valid measured original failure
is overall failed. Quarantine always invalidates comparison and prevents reset.
Observed verification/settlement/cleanup/evidence failures invalidate comparison
even when aggregate flags claim otherwise. Terminal operational failures differ
from a recorded recovered model/tool error followed by a correct original result.

### Typed phase transport and the launcher clock

The existing fixed commands exchange `ControlRequest` and `ControlResult` through
private run-specific files. The launcher supplies a request file at the fixed
trusted evaluator input path `/run/mcpbench/control/request.json`; that evaluator
writes `/run/mcpbench/control/result.json` within its own phase-specific mount.
These fixed paths are evaluator-only and never mounted in the agent. Only the
already declared prepare/settle-grade/finalize CLI values are allowed; no request
can add an executable, command-line argument, mount or environment variable.
Each invocation gets a fresh phase directory without replacing prior evidence.
All messages bind run/attempt/task IDs, task/config hashes, workflow and phase.
Control message_id, result.request_id and the next request.prior_result_id bind
the exact sequence; the host exit record repeats the delivered result message ID.

`ArtifactRef` is a bounded relative path under the trusted run root plus exact
byte count and SHA-256. It permits 2–4 bounded ASCII path segments and .json/.jsonl
files, excluding absolute paths, dot/dotdot segments and other suffixes. Runtime
code must additionally reject symlinks and verify actual bytes/hashes before
opening/consuming the file. A shape-valid reference is not filesystem evidence.
Prepare takes only task/fixture/config references; grade takes the previous phase
result and host agent-exit reference, plus agent result only when delivered complete.
Finalize takes its prior phase result and, only if verification was issued, the
host verifier exit and its complete result if available. Output names are fixed:
agent_request, agent_snapshot, verification_request, final_snapshot and evaluation.
Actual capabilities stay exclusively in separately prepared secret AuthInput files;
no control result, process exit or log contains their values or digests.

Prepare returns execute_agent, blocked or quarantine. Grade may return verify only
for an original passing invoice with an acknowledged initial fence and snapshot;
otherwise it returns finalize after known initial settlement or quarantine after
uncertainty. Finalize returns complete only with preserved final snapshot/evaluation
and the applicable acknowledged fence; quarantine never authorizes reset. A
ControlChain is a statically checked prefix or completed sequence, not runtime proof.
Blocked/quarantine decisions require a typed terminal Failure; successful launch
decisions cannot carry one. A skipped verifier has a typed verifier_skip_reason
(`read_only` or `original_failed`) carried unchanged through finalize. These decisions
and unique message IDs are private control data, never model commands or prompts.
Original_pass=true, including read-only completion, additionally requires the
host agent exit to be reaped, normal exited with code zero and no signal/timeout,
duration_ms <=300000, complete delivery and the matching agent_result reference.
ControlChain includes the parsed AgentResult for complete delivery and null for
other delivery states; its run/attempt must match and successful originals require
status=completed. A timed-out, signaled, nonzero, over-deadline or missing/bad result
cannot enable original PASS or verifier. After known process termination and initial
fencing, those failed originals may still grade/finalize safely without verifier.
Unreaped execution still requires quarantine. Finalize preserves the original verdict.
The next request's prior_phase_result ArtifactRef must equal the previous evaluator
host exit's complete-delivery result_ref, in addition to the prior message ID match.
These are structural checks on supplied records. They do not authenticate their
producer or prove that a parsed result came from particular external file bytes;
the launcher must verify actual paths, byte counts, hashes and parsed delivery.
Known parsed model/tool/retry counts must also fit the frozen 8/12/1 limits for
original PASS; validate_run_bundle checks them against the task's declared budgets.
Over-limit observations remain recorded in failed outcomes rather than clipped.

`ProcessExit` is produced only by the launcher. It distinguishes child/phase,
normal exit, timeout, termination and spawn failure; `reaped` states whether an
actual exit was observed. Exactly one exit_code or terminating signal is retained
for a reaped process, including a timed-out child that later exits normally. An
unreaped process has neither. Delivery independently distinguishes complete,
missing, partial, malformed and oversized results; only complete delivery has a
result reference. Complete delivery does not turn nonzero exit into success.
An unreaped agent cannot advance to authoritative grading/reset. Missing or bad
agent output is still a measured original failure after acknowledged settlement;
it cannot invent an AgentResult. An abnormal/missing verifier invalidates verification
and conservatively quarantines. Failed/missing evaluator output cannot advance a
chain: preserve the host exit record and quarantine, never fabricate its result.

The launcher establishes exactly one PostAgentBudget anchor immediately when the
agent finishes/is stopped. It alone measures elapsed time from its own monotonic
clock. All grade, verifier and finalize requests/results/host exits carry the same
anchor ID and UTC started_at/deadline_at (exactly 30 seconds apart for correlation).
`remaining_ms = max(0, 30000 - elapsed_ms)`; every invoked child/operation gets
`min(5000, remaining_ms)`. Results retain elapsed overruns, never clip observations.
No phase resets the anchor or increases remaining time. The chain checker compares
launcher budget observations in causal order and rejects restarted/regressing
budgets. It does not subtract unrelated producer clocks. Child-reported budget
echoes must be checked against the launcher's recorded deadline before acceptance.
At zero remaining time only quarantine may advance. Launcher restart fails closed
to quarantine in v1; restarting a phase never grants another 30 seconds.

`VerifierResult` is separate from AgentResult and retains the same identity, scope
and budget. It contains ordered attempted checks (at most two, retries zero), each
with its pass verdict, typed ToolResult or null plus typed terminal failure when
no valid response arrived. Same-payload success must return the bound invoice and
original payload; changed-payload success must be idempotency_conflict. Completed
requires both checks actually performed and passing. Finalize checks the host exit/
delivery independently, seals the verifier, compares the final settled snapshot
and preserves the original verdict. JSON validation does not prove those SQL acts.

### Required JSONL evidence and stream validation

Event payloads are closed per event_type. Model, tool and DB operations each have
started/completed/failed/interrupted events with source/phase/call correlation and
durations. Tool starts include validated arguments and retry index; completions
include typed ToolResult. Failures retain typed failure plus a nullable result if
no valid response exists. Model starts bind prompt/model hashes; terminal events
retain token counts or typed unavailable reasons. DB starts/terminals bind operation
and transaction ID: only MCP emits tool read/create/replay, and only evaluator emits
snapshot/seal/reset. No DB credential, SQL text or oracle rows are logged.

Retrieval completion requires exposed and authorized IDs plus catalog/query/schema
hashes and duration. Exposed IDs must be authorized. Fence events contain typed
receipts and matching status, grading events contain assertions/original verdict,
and process.exited contains the host-owned ProcessExit. Launcher may emit an explicit
operation.interrupted marker naming the producer, operation kind and call ID when
a killed producer cannot close its own started event. Run and cleanup events have
required outcomes/fingerprints; typed failure events retain bounded failure evidence.

Validate each JSONL line with the strict loader and Event, then validate the complete
trace with validate_event_stream (EventStream is its offline JSON-array equivalent).
The stream helper enforces unique event IDs, source-local contiguous sequences from
1, nondecreasing source-local elapsed time, run identity, unique operation IDs,
matching operation/source/phase/parent identity and closure of every start. An
explicit interruption closes that operation; a bare missing end is incomplete
evidence. Per-line document limits and the 100 MiB artifact cap remain binding.
No single event shape check claims the stream invariant or authenticates its source.

## Tables, tool behavior and pagination

`Tables` defines all application tables: customers, items, projects, timesheets,
invoices, invoice_lines and idempotency_records. Generated invoice/line IDs are
bounded business IDs; lines have contiguous `line_number` 1..N. Timesheets store
integer minutes, project and item references. Customer ownership is derived from
the project. Every persisted invoice has exactly one idempotency binding and one
to ten lines; row IDs/references, checked totals, ordered payload hash and row
counts must agree. Registry/capabilities are control data, not business seed rows.

| Tools | Precise behavior |
| --- | --- |
| billing_list_customers / billing_list_items | Empty args; all authorized active records sorted by ID; cap 100, explicit tool_error rather than silent truncation if more exist |
| billing_get_customer / billing_get_project / billing_get_timesheet | Exact ID lookup; include its active/billable fields as defined; unknown ID → not_found |
| billing_list_projects | Active projects; optional exact customer_id; stable project_id order |
| billing_list_timesheets | Optional customer_id via project, exact project_id, inclusive date_from/date_to against work_date; stable timesheet_id order |
| billing_list_invoices | Draft-only, optional exact customer_id, inclusive date_from/date_to against invoice_date; stable invoice_id order |
| billing_get_invoice | Exact invoice ID plus lines sorted by line_number; unknown ID → not_found |
| billing_create_draft_invoice | Validate active customer/items, canonical USD prices, dates, quantities and atomic idempotency rules above; due date before invoice date or overflow → invalid_arguments |

For paged list tools, omitted `limit` is 50 (range 1..100); omitted/null cursor
starts at the beginning. Return the corresponding array and `next_cursor`, null
at end. Cursor is unpadded base64url of `ASCII(last_id) + NUL + first 16 bytes of
SHA256(canonical {run_id, tool_id, filters})`; filters exclude cursor and limit.
Decode strictly, validate a bounded existing last ID in the same filtered set,
and compare query hash before keyset continuation. Malformed/mismatched cursor
is invalid_arguments, never SQL text. Cursor remains opaque to the model and is
not an authorization credential. No offset SQL is built from cursor text.

Tool input/output refs in the catalog are resolved from the local registered
schema before publishing complete object schemas in MCP tools/list and Ollama
function definitions; never send unresolved external refs to a model. Tool errors
use the shared bounded ToolError; unknown direct MCP tool/malformed JSON-RPC uses
the SDK's protocol error, while model-proposed unknown names are recorded without
dispatch. Error message text is sanitized, never raw DB/HTTP exceptions. Retryable
is true only for the bounded transient transport/DB cases, not domain denials.

## Canonical hashes and deterministic grading

Canonical hashed JSON has ASCII object keys sorted lexicographically, compact
commas/colons, UTF-8 strings preserved as Unicode scalars, standard JSON escaping,
no optional whitespace/newline, no HTML escaping, and integer numbers only. Do not
normalize Unicode values or sort semantically ordered arrays. `canonical_bytes`
and its test vector are authoritative for this profile; implementations must
match its bytes, including Unicode/control escaping, rather than assume default
language JSON encoders agree. Prices/quantities cannot use decimal/exponent forms.

Seed fingerprint hashes `{fixture_version,migration_version,tenant_id,tables}`,
sorting every table's rows by its declared primary key. Include every application
field, even generated values when rows exist. Exclude snapshot capture time, run/
attempt/stage metadata, registry, capabilities and fence receipts. Initial/reset
seeds are versioned immutable data; after-agent snapshots retain generated rows
for exact original/final comparison. `fixture_hash` hashes the full fixture object,
including its seed_hash; it is distinct from the seed fingerprint. Schema/catalog
file hashes in manifest.json hash raw committed bytes. Artifact manifests likewise
hash exact finalized bytes; no self-hash field is included in the hashed file.

The oracle compares all relevant tables with the declared permitted changes;
generated invoice/line IDs and timestamps may differ between independent trials,
but references, types, dates, quantities and totals must match fixed expectations.
The exact smoke task is CUST-001, SVC-CONSULT ×2 at 12,500 cents, 2026-11-07/21,
USD, tax zero, total 25,000 cents, one new draft and matching lines/idempotency row.
All other rows remain unchanged. Its prompt supplies IDs: create-draft is the
required set; list tools are optional relevant tools. Thus full-context smoke
precision is 3/3 and required recall 1/1; executed calls are a separate metric.

EvaluationResult preserves original task_success separately from run verification/
comparison validity. Null verdicts require explicit reasons; missing token components
make totals null while retaining known subtotals. A timeout cannot become task
success because a later snapshot is correct. Record denied attempts separately
from unauthorized execution (the latter must be zero). Dollar/energy figures are
null unless backed by declared measurement/rate or metered basis. Emit JSONL with
source-local sequences, UTC and local monotonic durations; do not subtract clocks
from different producers. Log wrong proposed names/rejected argument keys rather
than dispatch them; never log auth headers/raw capabilities/passwords/DSNs or raw
exceptions, and redact any secret before output. Explicitly label truncation.

## References and deferred proof

- [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12)
- [MCP tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
- [PostgreSQL row locks](https://www.postgresql.org/docs/16/explicit-locking.html)
- [PostgreSQL SELECT privileges](https://www.postgresql.org/docs/16/sql-select.html)

Only local contract tests run here. Actual MCP negotiation, SQL grants/isolation,
late-commit/fence acknowledgment, read-only grading, mount restrictions, JSONL
capture, model budgets and safe resets require the later admitted integration
tasks. Registry phase tests on JSON do not substitute for those experiments.
