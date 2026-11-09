# T019 context-overflow diagnosis — no fix applied

Candidate: `.worktrees/T019`, frozen `5c3dd4aa7550e3fc1632f455575cb9e5ff60fbc6`.
Observed run: `run-e19ac6733790474c4062544d`, attempt
`attempt-875c1532152f600038d47879`. Read-only FULL diagnosis; implementation and
runtime acceptance remain blocked. Production source and contracts unchanged.

Only sanitized `evaluator/agent/request.json`, redacted agent transport JSONL,
MCP business/DB trace, and local source/contracts were read. No auth/private/
controller credential files were read. No SQL, Docker, model, network, install,
resource reconfiguration, or native Ollama operations were performed.

## Exact failure

The agent successfully lists customers and items and creates the draft. Agent
`tool-3` and MCP `tool.completed` both retain invoice
`INV-1FE3C5398ABE8BC078918EEF8DF44A72`, USD total/subtotal 25000 cents, tax zero,
quantity two at 12500 cents. MCP DB `create_draft` completes. This is retained
execution evidence, not a substitute for independent settled database grading.

Immediately afterward `internal/agent/run.go:112–116` serializes the fourth
request, reserves 512 output tokens, and rejects it before `model.started` or
`Model.Chat`. `failure` is `context_overflow`; `agent.finished` reports failed,
model_calls=3, tool_calls=3, retries=0, empty final answer. The task/model timeout,
retry limit, authorization, and gateway are not the trigger.

| Next model turn | Exact serialized UTF-8 bytes | Bytes + reserved output | Remaining against 4096 |
| --- | ---: | ---: | ---: |
| 1 | 1717 | 2229 | 1867 |
| 2 | 2202 | 2714 | 1382 |
| 3 | 2785 | 3297 | 799 |
| 4, rejected locally | 3779 | 4291 | -195 |

The third assistant selection and draft result add 994 serialized bytes (263
and 731 including message-array separators), exceeding the previous 799 margin.
Fourth request components, serialized separately: messages 2376 bytes, complete
three-tool schemas 1275, model value 21, options 50, stream value 5; keys and
structural punctuation account for the remaining 52 bytes. It has all eight
history messages and all three authorized schemas. There is no duplicate SDK
text-plus-structuredContent ingestion: `mcp.go` selects structuredContent first.

The reconstructed first three request SHA-256 values exactly match retained
`model.started` hashes:

```
90d87dd0f0fa7c45460344c56d19404d010df5fd82f27a0c70f180642f849d03
ad54035ab6120011bea693f6282a4035a13d15f29dc55f3ac65280814f8a8626
be94d4022e82394ee3bdb15d2c062be82ca81257428031ac819979c5f64a3ddf
```

The reconstructed rejected fourth request SHA-256 is
`205284035680aa57a412950a1d2f6368840e7aabed188ea75425a132626f0dd4`.
There is no retained model-4 hash because admission rejects before emitting it.

## Conservative policy versus actual token overflow

This exactly follows the documented implementation policy:
`internal/agent/README.md` explicitly charges one token per serialized UTF-8 byte
plus output allowance and warns it can reject requests that a tokenizer fits.
The policy is stricter than the frozen 4096-context/512-output ceilings; the
normative evaluation contract requires those ceilings and retaining overflow,
not this particular byte estimator. There is no arithmetic bug or double
application of the 512 reserve. The estimator counts request options, model tag,
JSON syntax, and escaped JSON within message content; these are real wire bytes
but are not measured model tokens. That conservatism is deliberate. Whether this
request would actually overflow a native model cannot be established offline:
the scripted model returns null prompt/output counts, and model-4 never runs.
4291 is the guard's charge, not a measured tokenizer count.

Ranked hypotheses and distinguishing evidence:

1. Documented byte guard plus history growth: confirmed by exact hashes and
   actual Runner replay producing the same terminal event/counts.
2. Redundant internal result envelopes enlarge model history: confirmed by
   isolated representation counterfactual below; no business fields removed.
3. Extra scripted turns alone cause the excess: not sufficient as a one-turn
   optimization; pairing the list calls still exceeds the guard by 146 bytes.
4. Server result duplication or transport/gateway failure: contradicted by the
   normalized source path, identical agent/MCP business results, and offline
   reproduction without any transport or server.

## Smallest useful contract-preserving correction

Recommended source correction for review: retain validated frozen `ToolResult`
for internal control, tracing, error handling, and idempotency; project successful
tool-message Content to the complete validated business `Result` rather than
serializing the redundant internal `tool_id` / `is_error:false` envelope around
it. Keep all IDs, dates, names, prices, lines, totals, array order, timestamps,
assistant selections, correlation IDs, and full tool schemas. Preserve explicit
error messages/envelopes for unsuccessful tools. This changes presentation to the
model, not business output or frozen ToolResult contracts. `ollama.Message.Content`
is a generic string (`internal/ollama/client.go`); frozen AgentRequest/AgentResult
and ToolResult schemas do not prescribe a success-message Content envelope.
ToolName and ToolCallID correlation remain intact. Root may approve this as a
contract-preserving serialization correction under unchanged model settings; no
new context/output settings or benchmark-budget decision is needed. Retain current
redaction before supplying Content.

For these exact artifacts that representation saves **215 bytes** across the
three successful results. Fourth request becomes **3564 + 512 = 4076**, inside
the unchanged ceiling by **20**. This is a narrow fit, not evidence that arbitrary
larger fictional results fit; legitimate later overflows remain outcomes. The
scripted model's final-turn parser currently expects `agent.ToolResult`, so it
must consume the documented successful-business projection in the same reviewed
change. Do not weaken strict result validation or trust model totals.

The isolated measurement changes only the three successful message contents.
It is an offline counterfactual, not a production implementation or runtime
acceptance result. A virtual source overlay later exercised this exact projection
through actual Runner and reached completed/4/3/0; see checks below.
The regression seam should replay the complete captured-size schema/history
through actual Runner, assert a fourth final-answer turn, keep all result fields,
and retain a just-over-limit negative case. Existing fakeTools tests use tiny
`Synthetic tool`/empty-object schemas and therefore do not establish this fit.

Other options:

- Persist failed scripted AgentResult before returning a nonzero exit: independent
  necessary correction below, but it does not resolve context admission.
- Pair the two scripted list calls: saves only 49 bytes before any correlation-ID
  length changes, yielding 3730+512=4242; insufficient by itself. Skipping optional
  reads would narrow what the T019 full-stack scenario proves and is not a repair
  for this observed list/list/create workflow.
- A pinned tokenizer with exact supported prompt-template accounting could reduce
  estimator false positives, but needs model/version/template evidence and a
  separately reviewed measurement design. Ignoring the guard, replacing it with
  an unvalidated bytes/4 heuristic, dropping schemas/history/business fields, or
  enlarging ceilings is not recommended.

Core agent changes are outside the current T019 gateway owner's allowed lane.
Root must explicitly expand that source ownership before authoring the proposed
projection. FULL independent review/testing and a new frozen candidate/images
are required. If the chosen alternative changes architecture, security, frozen
budgets, or benchmark semantics, it needs the corresponding prior user approval;
this diagnosis supplies no such approval. A representation correction under
existing bounds does not itself require changing those contracts. Fresh resource
and connectivity admission remains mandatory before any future real runtime.
Retain the failed run and quarantined evidence; do not relabel it a success or
reuse/reset its state to validate a correction.

## Separate terminal-result delivery defect

`tests/integration/scripted-agent/main.go:128–131` returns immediately when Runner
returns a valid non-completed result, before assigning `value` or calling
`WriteResult` at line146. Thus the valid failed AgentResult exists in JSONL but
its required result document is missing. Production `cmd/agent/main.go:119`
writes valid results before returning an unsuccessful execution exit. Smallest
correction: align integration child's ordering with production: retain actual
status, close/flush events, write valid terminal result, then return nonzero for
non-completed status. Keep hard Runner/validation/write errors fatal; do not
invent success or skip failure retention. The same early-return pattern exists
in integration verifier mode and should receive the same bounded handling.

Missing evaluator AgentResult is therefore an effect of scripted CLI handling,
not evidence that Runner returned no result. Fixing it improves failure evidence
and allows the launcher/evaluator to inspect the actual failed outcome; it cannot
authorize verifier replay, PASS grading, or state reset for this failed attempt.

## Reproduction and actual checks

Owned ignored artifacts: `artifacts/diagnostics/t019-context/`.

1. `python3 artifacts/diagnostics/t019-context/replay.py` — PASS. Reconstructs all
   four exact requests, asserts retained hashes for first three and threshold
   crossing, measures business-only and paired-list counterfactuals. Uses only
   allowed sanitized artifacts and frozen embedded catalog/schema.
2. Actual Runner via a Go virtual test overlay (no candidate filesystem edits):

```
GOMAXPROCS=1 GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off \
  go -C .worktrees/T019 test -mod=readonly -p 1 \
  -overlay /home/sfkim/projects/mcpbench/artifacts/diagnostics/t019-context/overlay.json \
  ./internal/agent -run '^TestT019ContextDiagnosis$' -count=1 -v
```

Result: PASS, `ok mcpbench/internal/agent 0.213s`; actual Runner requests match
exact retained hashes and lengths, then actual Runner emits context_overflow with
failed/3/3/0. Replay uses synthetic in-memory auth, real validators/writer, fixed
in-memory model/tools, cached Go dependencies, and no sockets. PASS here means
the failure was reproduced; no successful business run is claimed. Candidate
`git status --short` remained empty. 3. Isolated success-projection experiment with actual Runner:

```
DIAG_PROJECT_SUCCESS=1 GOMAXPROCS=1 GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off \
  go -C .worktrees/T019 test -mod=readonly -p 1 \
  -overlay /home/sfkim/projects/mcpbench/artifacts/diagnostics/t019-context/projected-overlay.json \
  ./internal/agent -run '^TestT019ContextDiagnosis$' -count=1 -v
```

Result: PASS, `ok mcpbench/internal/agent 0.223s`; actual Runner completes with
model_calls=4, tool_calls=3, retries=0 and the exact server-returned invoice ID.
Requests are 1717, 2131, 2647, and 3564 bytes. Fourth request hash is
`7d14500996f30830c123f5b7de43a4bedc50f478e16eccbffd39c6362aa62510`.
The test compares every actual request to the full captured history after only
success-content projection; complete business fields, tools, and correlation
remain intact. Existing validation/redaction and 4096/512 guards execute in the
actual Runner. The final model response is an offline fixed answer, not native
inference. `projected-run.go` is an ignored diagnostic copy of frozen Runner with
only `if !result.IsError { b = result.Result }` inserted before message content
redaction. Go's virtual overlay reads that copy without changing candidate source.
This proves the focused serialization hypothesis at the Runner seam; it does
not test an authored scripted CLI parser change, error regressions, or real stack
acceptance.

Production correction, its regression suite, real stack retry, independent
database grading, and native-model token measurement remain **UNRUN**. No
production source fix or runtime operation was made during this diagnosis.
