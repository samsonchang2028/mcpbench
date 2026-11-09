# T018 lifecycle backend independent source review

Candidate: `047c030`, frozen `.worktrees/T018`; reviewed only `db/lifecycle.py`, `db/tests/test_lifecycle.py` and `db/LIFECYCLE.md`, with targeted reads of their frozen contracts, approved `db.manage` helpers, T016 caller and pinned psycopg source.

Verdict: **APPROVE for the adapter source review**. No concrete open P0/P1 identified. This is not approval of T018 runtime readiness or task completion; the operator/tester must supply admitted owned-container PostgreSQL evidence independently.

## Scope and findings

No source changes requested. The reviewed implementation preserves the intended trust and lifecycle boundaries:

- Production configuration admits only the fixed private config/passfile locations and dedicated `db:5432/mcpbench` endpoint. It rejects extra/duplicate keys, wrong types, inherited alternate PG connection configuration, broad passfiles and same controller/grader passwords. Descriptor-relative opens reject symlink path components; private files require current ownership, regular mode0600 and bounded bytes, and the control directory requires mode0700. Raw exceptions are replaced by bounded contract errors; known secrets remain private trusted redaction input.
- Controller/grader factories and fresh connections are distinct. Both connection identity and SQL effective identity are checked. Grader reads use one REPEATABLE READ READ ONLY transaction, so the returned registration and application tables share one snapshot. Mapping validation binds trusted RunScope and the frozen derived schema; no model-controlled identifier/URL/DSN/shell path exists.
- One absolute monotonic deadline covers DNS, connect, driver waits, queries, transaction acknowledgment and return. The driver subclass closes its socket on timeout/interrupt instead of using psycopg's ordinary cancellation grace. The post-operation checks reject late ACKs. Failures and interrupts poison the run on this backend instance, preventing follow-up read/reset/retry calls; source never retries uncertainty or writes a speculative quarantine state.
- Controller transitions lock the registry FOR UPDATE before application access. Fences require the fresh executing/0 or verifying/1 state, revoke both digests and verifier scope, increment generation, and emit a positive receipt only after acknowledged commit and deadline checks. The zero-in-flight claim is conditional on the separately required service FOR SHARE invariant, explicitly documented rather than inferred from cancellation.
- Reset rejects active/terminal/poisoned states, checks exact fixture/version/checksum/inventory and bounded coherent tables, deletes only the seven registered tables in FK order, and reseeds/verifies through the approved helper within the same transaction. Mark-cleaned checks the canonical seed fingerprint under the registry lock. No schema drops, CASCADE, global reset or resource cleanup occurs.
- Verifier activation checks draft workflow, sealed generation, matching request scope/key and exact saved ledger invoice/hash before installing the narrow verifier scope. No activation path repairs a missing invoice. The caller remains responsible for original correctness, persisted evidence and the absolute post-agent budget.

## Pinned psycopg compatibility checked by reading actual installed source

Inspected the existing T008 environment at `/home/sfkim/projects/mcpbench/.worktrees/T008/.venv/lib/python3.14/site-packages/psycopg/` (selected version 3.3.8):

- `_connection_base.py`, `_connect_gen`: yields the libpq connection generator and constructs `cls(pgconn)`, preserving the `_DeadlineConnection` subclass.
- `connection.py`, constructor: defaults to tuple rows and ordinary non-autocommit transaction behavior; the bypass of public connect does not require a missing row-factory setup for this adapter.
- `waiting.py`, `wait_conn` and wait implementation: accept `interval` and `timeout`; the code's bounded-call signatures match the pinned API. The resolved single IPv4 `hostaddr` avoids a second blocking hostname lookup during libpq connect.
- `transaction.py`, transaction enter/exit and commit/rollback generators, plus `connection.py` transaction context: transaction control is driven through the connection's wait hook. Thus the override covers COMMIT/ROLLBACK as well as query waits.
- `connection.py`, `close`: directly finishes the libpq connection and does not enter the ordinary connection wait/cancel grace path.

These are source compatibility observations, not a live network timing result. The implementation intentionally relies on pinned private driver primitives; changing psycopg requires renewed compatibility and timeout acceptance checks.

## Caller alignment and remaining gate

T016 uses `capture(..., 'agent_only')` when verification is skipped, including read-only completion; it requests `'final'` only after verification. Therefore this backend's final/2 check does not incorrectly demand a verifier fence for read-only completion.

Per-instance poisoning is not durable quarantine across new evaluator processes. The implementation and documentation explicitly place persistent quarantine/no-relaunch decisions with the trusted launcher. Reconstructing an adapter must never be treated as recovery authorization. Likewise the backend cannot establish that external snapshots were persisted before reset; T016 owns that gate.

Reviewer executed **no tests, connections, SQL, model requests, Docker commands or source/Git mutations**. Authored mock checks were inspected, not counted as actual runtime proof. Root owns the offline test results and admitted live database validation. Actual dedicated-container/image/network identity, grants and role isolation, concurrent FOR SHARE/FOR UPDATE fencing, post-wait revocation checks, rollback/seed equivalence, and real timeout/lost-ACK behavior remain **UNRUN in this reviewer lane**. T018 readiness remains gated on those independent results.
