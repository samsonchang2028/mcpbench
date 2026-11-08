# T017 independent tester report

Candidate: `d443fee3a8c0e6c2a13c40f8d284ef446ed673bd`, fixed in
`.worktrees/T017`, compared with `272ce58`.
Verdict: **PASS for the approved T017 library scope**. No findings.

This tester did not author the candidate and changed no candidate source/tests.
The candidate is six files exclusively under `observability/`. HEAD and clean
worktree were verified before and after testing. The appended task context's Go
full-validator callback boundary is the acceptance scope; this report does not
claim application/runtime instrumentation is ready.

## Executed commands and results

From `/home/sfkim/projects/mcpbench/.worktrees/T017`:

```sh
PYTHONDONTWRITEBYTECODE=1 /home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python -W error::ResourceWarning -m unittest observability.test_jsonl contracts.tests.test_contracts eval.fixtures.test_fixtures -v
GOMAXPROCS=2 GOTOOLCHAIN=local GOPROXY=off MCPBENCH_TEST_PYTHON=/home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python go test -mod=readonly -p=1 ./observability -count=1
GOMAXPROCS=2 GOTOOLCHAIN=local GOPROXY=off go vet -mod=readonly ./observability
git diff --exit-code 272ce58..d443fee -- contracts eval/fixtures go.mod go.sum pyproject.toml uv.lock
git diff --check 272ce58..d443fee
git status --short
git rev-parse HEAD
```

- Python **PASS**: 57 tests, zero failures/errors/skips; this is 11 observability
  tests plus the candidate's existing 46 contract/fixture tests. ResourceWarning
  is promoted to error. Synthetic library tests do not imply real trace evidence.
- Go **PASS**: nine test functions and their subcases; package result
  `ok mcpbench/observability 3.304s`, exit 0. Tests require the real authoritative
  Python Event validator through the documented bounded, test-only bridge.
- Go vet **PASS**, exit 0, no output.
- Frozen contracts, fixtures and dependency manifests **PASS**, no byte changes
  against baseline in the scoped Git comparison above.
- Whitespace **PASS**; final candidate **stable and clean**, full hash as above.

## Acceptance evidence

- **Trusted metadata, time and correlation — PASS.** Tests exercise run/attempt/
  source context, generated event IDs, contiguous sequences, UTC timestamps,
  controlled monotonic elapsed values, call/parent identity, model/tool/DB
  correlation, missing start, changed identity and reused operation rejection.
  Legitimate numeric prompt/output token counts survive serialization.
- **Contract validation and invalid inputs — PASS.** Python invokes authoritative
  Event validation on the final redacted object. Go requires a nonnil trusted
  full-Event callback; missing/rejecting validators fail closed. Tests use the
  actual frozen validator for successful and rejected events, including nested
  tool arguments, negative duration, unavailable-count consistency, source/phase
  restrictions, unknown types, invalid Unicode and nonfinite/arbitrary objects.
  Runtime callback implementation remains T019 work.
- **Redaction and safe errors — PASS.** Nested sensitive keys and known literal
  secrets, recognizable Bearer/credential-bearing text, metadata secrets and
  secret-bearing data keys are exercised. Arbitrary formatter/marshaler/error
  objects are rejected. Emitted errors retain sanitized categories rather than
  underlying private I/O/validation text. Numeric usage fields are preserved.
- **Bounds and completeness — PASS.** Tests cover line/file/event caps, bounded
  traversal, regressing clock, empty files, unclosed operations and post-close
  emissions. Invalid input or logging failure poisons completeness rather than
  silently dropping an event or reporting trial success.
- **Durability and exclusive files — PASS.** Unit tests use real temporary local
  files and injected write/short-write/sync/close faults. Files are mode 0600,
  existing files and final symlinks are rejected, successful bytes/counts follow
  acknowledged sync, and close propagates prior errors without retry. Ancestor
  ownership/path admission and aggregate run caps remain launcher obligations.

## Independent adversarial probes

Executed an additional inline Python script (no source file added), using the same
cached interpreter, bytecode disabled and ResourceWarning promoted to error. It
created temporary local files and asserted these four groups, all **PASS**:

1. After a valid model start, mutate both the original caller dictionary and
   returned Event dictionary, then emit a correctly correlated completion. Close
   succeeds; strict persisted-line loading and authoritative EventStream validation
   pass; stored start identity is unchanged.
2. Measure an actual emitted start-line length including newline. A writer capped
   at that exact length accepts the line; a cap one byte smaller rejects with
   `capacity` before accounting any events/bytes. The accepted unfinished start
   still fails close with `unclosed_operation`.
3. After the capacity failure, an unrelated malformed later event and repeated
   close retain the first `capacity` error; artifact completeness stays false.
4. Nested credential fields containing otherwise unsafe object values are discarded
   without formatting/traversal, unknown Bearer text and registered literal secrets
   are redacted, and numeric prompt/output usage remains 12/7.

## Scope and unrun evidence

No SQL/database connection, container/image/model operation, inference, network
probe, dependency installation, service change or Git mutation occurred. Only this
report was written in the main worktree. Go test's Python subprocess is explicitly
test-only and bounded to five seconds per validation call; the Go library starts
no runtime subprocess.

The known undotted `failure` EventStream bug is outside this candidate and is
already fixed separately on main per the supplied context. Candidate tests verify
failure Events individually; the independent full-stream mutation probe above uses
a model start/completion pair. The post-merge combined-source check including the
separate failure-stream regression is **UNRUN here** and remains the orchestrator's
integration check. Actual T019 callback wiring, application event completeness,
real benchmark traces and T021 fairness/metric acceptance are **UNRUN**, not claims
of this library gate. Source-local close does not prove complete multi-source
trace or successful benchmark lifecycle.
