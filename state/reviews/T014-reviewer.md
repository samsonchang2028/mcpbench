# T014 independent review

Candidate: `2db9a23` versus `ad6833f`, inspected in `.worktrees/T014`.
Reviewer: independent of T014 implementation. Verdict: **CHANGES REQUIRED**.
No source changes, workload execution, SQL, containers or inference were performed.
The orchestrator owns independent cached test results; this report records static
review findings, not an additional executed-test claim.

## P1 — Successful conflict verification emits a terminal verification failure

Location: `internal/agent/verify.go:117–125`.

Trigger: the second fixed verification call correctly returns
`idempotency_conflict`. Lines 109–110 set `check.Pass=true`, but lines 122–125
unconditionally emit `tool.failed` containing a terminal `verification_failed`
Failure for every error-shaped ToolResult, including that expected successful
conflict. The returned VerifierResult is nevertheless `completed` with two passing
checks. Thus every happy-path verifier produces contradictory outcome evidence.

Impact: complete failure accounting must retain this terminal verification failure
and invalidate comparison, even when replay flags claim success. Ignoring it in
later aggregation would instead conceal an observed terminal safety failure. The
current shape/stream parity tests accept the contradiction because they do not
cross-bind verification events to the successful verifier verdict.

Fix: keep the typed error-shaped tool response, but distinguish an expected
successful conflict from failed verification when choosing its Failure code and
disposition. Do not emit terminal `verification_failed` for a passing check. Add
an assertion that a successful two-check verifier trace contains no terminal
verification failure, while retaining actual failed-check evidence.

## P1 — The runtime Event callback omits calendar and date-order semantics

Locations: `internal/agent/events.go:32–38,75–123` and
`internal/agent/validate.go:27–56`.

Trigger: take an otherwise valid create-draft ToolResult and replace its invoice
date with `2026-02-30`, its created_at with an impossible calendar timestamp, or
make due_date precede invoice_date while preserving the money/line fields. The
schema's Date/UTC patterns still match. The cached jsonschema-go v0.4.3 validator
does not enforce the Format keyword; the additional DecodeToolResult checks
inspect line references and arithmetic but never parse invoice dates/timestamps
or compare invoice/due dates. ValidateEvent therefore admits such nested results.
The authoritative Python validator rejects them through FormatChecker and
`_walk`'s due-date ordering check.

Impact: the required callback is not a full semantic validator even for the
emitted three-tool subset. Invalid server results can enter model feedback and
durable events as successful completions, and fail only when later Python trace
validation runs. Existing negative parity cases cover count availability and
arithmetic/result identity, but miss these format/order cases.

Fix: enforce actual calendar formats and invoice/due ordering on nested draft
results, plus calendar validity for emitted UTC fields. Add matching Go/Python
negative parity cases. Preserve the existing server-authoritative money behavior.

## P1 — Verifier startup does not consume or cap the supplied remaining budget

Locations: `cmd/agent/main.go:63–78` and `internal/agent/verify.go:60–68`.

Trigger: a valid request carries a small remaining_ms observation while its UTC
deadline is farther away, which the frozen schema permits and a conservative
launcher observation can produce. The CLI sets only the absolute UTC deadline,
then permits ConnectMCP up to five seconds. Verify starts its local elapsed timer
only after that connection completes and grants the unchanged remaining_ms again.
For example, a supplied 100 ms remaining observation can authorize a connection
lasting substantially longer than 100 ms before the verifier loop starts.

Impact: the verifier's initial MCP negotiation can exceed the applicable remaining
budget and five-second/remaining operation rule. Connection/startup time is absent
from its local observation. A host deadline is an additional control, not a reason
for the child to issue work beyond its supplied stricter budget.

Fix: establish one local budget observation before connection, bound the entire
verification invocation by min(supplied remaining, absolute deadline), cap the
connection operation by min(5000 ms, remaining), and carry consumed startup time
into Verify and its returned observation. Test a slow scripted connection with a
small remaining budget and a later wall deadline; assert no verification call
occurs after exhaustion and elapsed observations retain the startup cost.

## Residual observations and accepted scope

* P2: `internal/agent/files.go:17` opens inputs without O_NONBLOCK before checking
  regular-file type. A FIFO input can block before the application establishes
  its context. The launcher is required to reject unexpected types before launch;
  adding a nonblocking open would also make this library boundary fail promptly.
* Fixed verbs/flag order, separate AuthInput, fixed loopback HTTP targets, disabled
  proxies/redirects, strict duplicate/raw argument rejection, bounded retries,
  exclusive result publication and non-noop semantic checks are present. No
  arbitrary command/tool execution path was found in the reviewed surface.
* The selected cached SDK's `server/discover` handshake for protocol 2026-07-28
  is accepted. Business structuredContent/direct ToolError normalization matches
  the frozen internal envelope requirement; it is not a finding.
* Runtime source starts no Python validator process. Test-only Python parity is
  clearly separated. Real MCP/Ollama/DB behavior and combined producer wiring
  remain explicitly UNRUN pending later tasks; no live success is claimed.

Re-review the three P1 fixes and their focused evidence before approving this
candidate. Approval would not authorize runtime startup or deployment.
