# T017 independent reviewer

Candidate: `d443fee3a8c0e6c2a13c40f8d284ef446ed673bd` in `.worktrees/T017`, compared with `272ce58`.
Verdict: **APPROVE** for the approved T017 library/seam scope. No P0/P1 findings.

## Inspected evidence

Reviewed the six changed observability files, documented API/limits, Python and Go writer implementations and tests against the T017 context and retained frozen Event/EventStream requirements. Candidate HEAD and clean source state verified. No application, contract, fixture or dependency files change.

- Python constructs trusted source-local envelope fields, redacts data, then invokes authoritative `validate('Event', event)` before encoding or writing. Go rejects a nil Validator and passes the final redacted Event to its required trusted full-contract validator before persistence. The explicitly approved Go callback seam has no permissive default; documentation requires complete semantic/nested validation and nonmutating behavior. The Python subprocess bridge exists only in Go tests, has a five-second deadline and does not add runtime process execution or dependencies.
- Both redactors copy bounded JSON trees, reject unsupported/nonfinite/invalid-Unicode data, bound traversal depth and data budget, remove credential-named values and recognizable credential text, replace registered secret literals and reject secret-bearing data keys/metadata. Numeric prompt/output token fields are preserved. Closed Event validation still rejects forbidden envelope/config/oracle fields rather than silently disguising an auth envelope. Unknown arbitrary secrets in text remain a caller obligation, explicitly documented with safe typed failures and known-secret registration.
- Trusted run/attempt/source, event IDs, source-local contiguous sequences, UTC timestamps and monotonic elapsed times are constructed by the writers. Local operation state rejects missing starts, reused IDs, phase/parent mismatches and changed tool/model/DB identities. Python stores correlation state independently of its returned event; Go redaction copies caller data. Registered standalone failure records do not implicitly close pending operations.
- Default record/file/event caps and lower custom limits are enforced before write, within the frozen maximum ceilings. Line limits include newline. Per-file caps are correctly distinguished from the aggregate run artifact cap, which remains a launcher obligation. Open/empty/incomplete files cannot receive a successful completeness summary.
- Files are created exclusively mode0600 with final-path and immediate-parent symlink defenses, parent-directory fsync and no truncate/resume/append behavior. Successful writes require full byte count and file fsync before counters/correlation state advance. Full ancestor ownership/path validation remains explicitly assigned to the trusted launcher.
- Validation, correlation, clock, capacity, write/short-write/sync and close errors produce stable sanitized categories and poison later output. Close still attempts durability/closure after failure and retains the original error; physical partial files remain incomplete evidence. Calls and summaries are serialized. No automatic retry, background worker, network access or telemetry framework is introduced.
- Tests exercise authoritative Event validation, trusted context, sequence/clock/correlation, invalid arguments/counts/durations, metric-preserving credential redaction, caps, exclusive/symlink rejection and injected write/sync/close failures. Test-only synthetic evidence is not represented as a working benchmark trace.

## Required independent evidence and runtime limits

Independent tester execution/contract-parity results remain required before integration; this reviewer did not duplicate checks or claim an observed PASS. Only this report was written. No source/Git change, install, DB/SQL, image/container, network/model call or inference was performed.

The approved Go Validator seam is a mandatory T019 integration obligation, not implemented runtime semantic parity. Combined traces must still be strict-loaded and accepted by the authoritative EventStream validator, including cross-source interruption/closure; local Close does not prove multi-source completeness or trial success. Main's independently accepted undotted-failure parser correction `1c013d0` must remain in the integrated validation baseline. T019/T021 also retain actual producer wiring, full lifecycle ordering, durable manifest/summary, aggregate budgets, metric attribution and runtime proof. Host path ownership/ancestor checks and all live instrumentation behavior remain UNRUN.

No contract drift or unresolved review finding was identified. Approval does not authorize workloads, deployment, inference or task completion.
