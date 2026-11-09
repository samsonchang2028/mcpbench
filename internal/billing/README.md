# T012 billing seam for T013

`billing.Service{Repo: store.New(source)}` supplies the three frozen tools. The
source implements `BeginTx(context.Context, pgx.TxOptions) (pgx.Tx, error)`; a
trusted dedicated service connection or concurrency-safe connection source can
supply it. A single `pgx.Conn` is not safe for concurrent calls. No constructor
opens a connection or resolves environment credentials.

- `Authorize(ctx, Access) ([]string, error)` authenticates initialize/list through
  a registry-locked transaction. Use the returned ACL to filter the frozen catalog.
- `Call(ctx, Access, toolID, json.RawMessage) (any, error)` authenticates and parses
  exact model arguments. Success is `CustomerOutput`, `ItemOutput` or `DraftOutput`,
  ready to place in the frozen `ToolResult.result`. Reads require `{}`. Lists are
  active-only, ordered by ID, and reject more than 100 active rows rather than
  truncate. Inactive rows do not count against the list cap; draft validation
  retains inactive records to distinguish `inactive_record` from `not_found`.
- `Access{RunID, AttemptID, IdempotencyKey, Capability}` is private trusted transport
  metadata. There is no schema, tenant, price, invoice ID or SQL input route.
  Never expose Access to the model or construct it from tool arguments.
- `*billing.Error` has frozen ToolError JSON fields `code`, `message`, `retryable`.
  Use `errors.As`. Map it into `ToolResult.error`; internal `OutcomeUnknown` is
  excluded from JSON and must be retained by trusted settlement diagnostics.
  Messages are bounded categories and never contain SQL, credentials or raw input.
  Other unexpected adapter errors require a bounded nonretryable `tool_error`.

Every call (including authorization) gets at most five seconds, shortened by the
caller's deadline. The same context covers pool/connection acquisition, locks,
reads, writes, COMMIT and rollback. No detached operation or internal retry exists.
An absent or late positive COMMIT ACK discards the result and returns `db_error`
with `OutcomeUnknown=true`, `retryable=false`. A missing rollback ACK also returns
unknown. Neither timeout nor cancellation proves that a write was rolled back.
The caller owns the frozen single transient-retry budget and original task deadline.

Domain arithmetic uses integer cents, canonical server prices and checked sums
bounded by 2^53-1. Dates, active IDs, USD, duplicate items and positive quantities
are checked before SaveDraft. Strict parsing rejects duplicate/unknown/case-varied
keys, noninteger lexical quantities, excessive depth, invalid UTF-8 and trailing
JSON. `PayloadHash` matches the frozen sorted-key canonical JSON protocol; line
order matters. The implementation does not import the independent grading oracle.

The verifier uses the saved invoice to reconstruct the original arguments and
verify the original ledger hash. Only exact replay or the frozen first-quantity
+1 (or -1 at 1000) conflict payload is admitted. Other valid payloads are denied.
Missing ledger/invoice is `verification_not_replayable`, with no create branch.
Verifier calls never acquire the write-key lock or call SaveDraft.

## Actual T012 checks and limits

With Go 1.26.8, pinned pgx v5.11.0 and the existing T008 Python 3.14.4 environment:

```sh
MCPBENCH_TEST_PYTHON=/home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python GOMAXPROCS=1 GOTOOLCHAIN=local GOPROXY=off go test -mod=readonly -p=1 ./...
```

Results are recorded in the candidate handoff. Unit checks exercise canonical
hash parity with `contracts.validate.payload_hash`, strict arguments, exact and
overflow arithmetic, active/missing records, duplicate items, replay/conflict,
verifier scope, locked authorization ordering, SQL routing, role checks, positive
ACK failure handling and bounded error classification. They are test-double proof,
not PostgreSQL privilege, concurrency, fencing or live MCP proof.

Author check, 2026-11-08: the command above **PASS** across all Go packages,
including the contract hash parity subprocess and observability tests. The three
opt-in PostgreSQL tests **SKIP / UNRUN** without database admission. No database
connection, dependency installation, image/container operation or inference ran.
Independent reviewer/tester acceptance and actual PostgreSQL proof remain pending.

Active-list repair check, 2026-11-08: cached-dependency `go test -mod=readonly
-p=1 -count=1 ./...` with the same environment above **PASS**. New offline cases
cover both list tools with mixed/descending records, more than 100 inactive
records, exactly 100 active records, 101 active records returning `tool_error`,
and retained inactive-versus-missing draft validation. These use test doubles;
PostgreSQL list execution and other live DB gates remain **UNRUN** here.
