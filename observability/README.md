# Bounded local JSONL adapters — T017

This package supplies Python and Go writers for later application wiring. These
are library tests using synthetic events; no real benchmark trace, inference,
SQL, MCP session or runtime instrumentation is claimed. There are no new
package dependencies, background workers, network calls or runtime subprocesses.
T019 owns wiring, and T021 owns metric/fairness acceptance.

## Python

```python
from observability import JsonlWriter

writer = JsonlWriter(path, run_id, attempt_id, "agent", secrets=known_secrets)
try:
    writer.emit("model.started", "agent", "ok",
                {"model_digest": model_hash, "prompt_hash": prompt_hash},
                call_id="model-one", parent_call_id="agent-operation")
    # Actual model call occurs elsewhere; keep unavailable counts explicit/null.
    writer.emit("model.completed", "agent", "ok",
                {"model_digest": model_hash, "prompt_hash": prompt_hash,
                 "duration_ms": measured_ms, "prompt_tokens": prompt_tokens,
                 "output_tokens": output_tokens, "counts_unavailable_reason": None},
                call_id="model-one", parent_call_id="agent-operation")
finally:
    writer.close()  # Raises LogError if anything failed or an operation is open.
summary = writer.summary
```

`emit` constructs trusted version/run/attempt/source/ID/sequence/time metadata,
redacts data, then calls the authoritative frozen `contracts.validate.validate`
for **Event shape and semantics**, including nested objects. It returns the
persisted event only after write and fsync. Returned dictionaries can be modified
without changing stored correlation state. `monotonic` and timezone-aware
`wall_clock` are injectable for deterministic tests; defaults use source-local
monotonic time and UTC. Elapsed durations must not regress; wall stamps normalize
to UTC with six fractional digits. Operation duration fields are supplied by the
caller from its own measured monotonic intervals, validated and never clipped.

## Go

```go
writer, err := observability.New(path,
    observability.Context{RunID: runID, AttemptID: attemptID, Source: "agent"},
    observability.Options{Validate: validateFullFrozenEvent, Secrets: knownSecrets})
// Check err; then Emit(Record{Type: ..., Phase: ..., Status: ..., Data: ...,
//                           CallID: ..., ParentCallID: ...}) and Close().
// Check every returned error and writer.Summary().ArtifactComplete.
```

Go requires a nonnil trusted `Validator func(map[string]any) error`. It receives
only the **final redacted Event** and must validate the complete frozen contract,
including semantic rules and nested objects. A schema-only checker or permissive
callback does not satisfy that obligation. The validator must not mutate/retain
its argument or panic. T019 **MUST wire a real validator/reuse validated domain
data and add parity tests before accepting actual Go telemetry**. The required
callback seam is not proof that runtime validation is implemented. No domain
validator is duplicated here. Tests alone bridge the real frozen Python validator
using a bounded five-second subprocess; the runtime Go package starts none.

`Record.Data` accepts strict JSON trees: `map[string]any`, `[]any`, strings,
booleans, nil and primitive Go integer/finite float types. Arbitrary structs,
custom marshalers, raw JSON and arbitrary errors are rejected rather than invoking
their formatting/marshal methods. `Options.Now` defaults to `time.Now` and should
preserve its monotonic component. Go writes UTC stamps at microsecond precision
and calculates elapsed milliseconds from that clock. `Emit` returns only an error;
`Summary` returns counts, bytes, open operations, closed/completeness and a stable
sanitized error category. Zero-valued Go numeric options select defaults; Python
explicit zero limits are invalid.

## Bounds, redaction and durability

Both adapters default to 1 MiB per line **including the newline**, 16 MiB per
file and 2,500 events. Callers may lower limits; ceilings are 1 MiB, 100 MiB and
10,000 respectively. Recursive data traversal is additionally bounded by depth32
and a 1 MiB budget for nodes/string/key bytes before encoding. Sensitive values
are discarded without visiting their contents. The entire run's 100 MiB budget
covers all producers and other artifacts; the trusted launcher must enforce that
aggregate cap separately. A per-writer file cap does not reserve aggregate space.

Known secret literals are replaced in strings; credential-named fields and
recognizable Bearer tokens, password/key assignments and credential-bearing URLs
are redacted. Numeric `prompt_tokens`/`output_tokens` are preserved. Secret literals
in metadata or data keys are rejected, preserving correlation instead of silently
rewriting IDs. Redaction leaves field names: closed Event validation still rejects
unexpected auth/credential/oracle/config fields. Do not submit entire auth envelopes,
expected states, snapshots, database configs or raw exceptions. Use typed safe
Failure categories/reasons and register **every known secret**. Pattern matching
cannot discover an otherwise unrecognizable unknown secret embedded in arbitrary
text. Error returns contain fixed categories, never underlying exceptions/paths.

A writer creates one new mode0600 file, exclusive and without following its final
symlink or immediate-parent symlink. Creation fsyncs the parent directory; each
successful emit writes one complete line and fsyncs the file. The launcher still
owns validation of the entire ancestor tree, run ownership and allowed mount
paths. Writers do not resume, truncate, replace or append to existing files.
One writer is allowed per `(run_id, attempt_id, source)` for an attempt. ID generation
and sequences are source-local; multiple independent writers for one source would
produce collisions and are forbidden. Calls are serialized by a lock.

Any schema/semantic/correlation/capacity/clock/write/short-write/sync failure poisons
the writer. Later emits fail without retry, and close still attempts sync/close
then reports the original error. Partial physical bytes may remain after an I/O
failure; summary byte/event counts include only successfully synced records.
Preserve failed files as incomplete evidence; never turn them into trial success.
Empty files and unclosed model/tool/DB operations are incomplete. Repeated close
is safe and returns any prior error; emitting after close poisons completeness.
This API does not atomically finalize a whole run manifest or replace other
artifacts: the trusted launcher owns those lifecycle operations.

## Correlation and complete-trace acceptance

The writer enforces unique local operation IDs, start-before-terminal,
source-local contiguous sequence, nondecreasing elapsed time, and matching
phase/parent/tool/model/DB identity. Valid event kinds come from the frozen
contract; no new event fields/types are added. Each source has one independent
clock; never subtract timestamps from separate producers to claim latency.

A successful local close is **not** proof of complete multi-source evidence.
The evaluator must strict-load every persisted line and run
`contracts.validate.validate_event_stream` over the assembled trace. A launcher
`operation.interrupted` can close a killed producer's open operation only in that
combined trace; it cannot repair that producer's file or hide its failed close.
Protocol lifecycle, authoritative receipts, operation results, metrics and trial
success still require independent runtime evidence. A missing end is never an
implicit successful operation. At authoring time, the frozen stream helper's
`failure` event split bug was reported to the orchestrator; writers support that
registered type, and no contract change is made in this lane.

## Checks

Use the existing pinned T008 environment read-only. No install/download is needed.
From the repository root, adjusting only the existing environment path as needed:

```sh
/home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python -W error::ResourceWarning -m unittest observability.test_jsonl -q
MCPBENCH_TEST_PYTHON=/home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python GOMAXPROCS=2 GOTOOLCHAIN=local GOPROXY=off go test -mod=readonly -p 1 ./observability -count=1
GOMAXPROCS=2 GOTOOLCHAIN=local GOPROXY=off go vet -mod=readonly ./observability
```

Tests cover real contract validation/parity, trusted context, contiguous sequences,
correlation/identity/reuse, finite data, negative duration, invalid tool arguments,
metric preservation, nested credential/text redaction, limits, clock regression,
exclusive/symlink-safe creation and injected write/short-write/sync/close failures.
