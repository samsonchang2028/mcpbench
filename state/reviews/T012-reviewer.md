# T012 independent review

Candidate: `77f3e893981b1c54284896b64585a928a12a0d57` in `.worktrees/T012`, compared with `ad6833f`.

Verdict: **CHANGES REQUIRED**. One open P1; no P0 identified in this static review.

## P1 — List tools return inactive records and count them against the active-list cap

Locations: `internal/store/store.go:216`, `internal/store/store.go:239`, and the direct result forwarding in `internal/billing/billing.go:142` / `:155`.

Trigger: a registered synthetic run contains an inactive customer or item. Both repository queries select every row, without an active predicate, and the service returns those rows unchanged. A valid `{}` list request therefore exposes inactive records. More than 100 total rows also produces `tool_error` even when the authorized active set is within its limit.

Impact: this violates frozen `contracts/PROTOCOL.md:386`, which specifies all authorized **active** records, sorted by ID, with the cap applied to that result set. The present canonical fixture contains only active records, so existing smoke-oriented doubles do not reveal the defect.

Smallest useful fix: give the list branches an active-only bounded query/path and apply the 100-row cap after active filtering. Keep create validation able to distinguish a known inactive ID from a missing ID; simply filtering the existing shared `Customers`/`Items` methods would turn that path into `not_found`. Add focused cases with active/inactive mixtures, stable ordering, and more than 100 inactive rows alongside a valid active set.

## Reviewed invariants

Static inspection covered the complete billing/store changes, their tests and API documentation, the frozen component protocol, canonical fixture, registry/bootstrap grants and application migration constraints.

- Money uses server-side integer prices, checked multiplication and checked sum against `2^53-1`; zero tax, USD and draft status are constructed server-side. Strict arguments reject unknown/duplicate keys, decimal/exponent quantities, invalid dates and duplicate item IDs. Canonical payload hashing preserves line order and uses only validated ASCII business IDs/dates.
- The store opens READ COMMITTED transactions, bounds the operation to five seconds or the caller's shorter context, and sets local statement/lock limits. The registry `FOR SHARE` precedes application access; authorization checks phase/generation, digest, expiry, principal, allowed tools and exact registered schema while holding that lock.
- Database routing uses quoted registered identifiers and parameterized values. Both login and effective role must be the dedicated service role. The supplied bootstrap limits service registry mutation to the inert lock column, and source issues no registry/business updates or resets.
- Same-key execution creates take a transaction advisory lock before reading the ledger. Header, lines and ledger share the transaction. Callback results are discarded on errors and any missing/late positive COMMIT acknowledgment; unknown settlement remains explicit and nonretryable.
- Verifier authorization restricts the tool/key and validates its bound scope. The domain branch checks the existing invoice/hash, reconstructs and rehashes original arguments, admits only exact replay or the constrained first-quantity change, and cannot reach `SaveDraft` or the write-key lock when the original is missing.
- The public T013 seam is documented: trusted `Access`, per-request `Authorize` / `Call`, typed business results and bounded `billing.Error`, with private `OutcomeUnknown` excluded from public JSON. No dependency or frozen contract change was introduced.

## Evidence limits

This review ran no tests, database connections, SQL, model requests or container operations. It inspected authored unit/test-double cases and opt-in PostgreSQL tests; their presence is not a PASS claim. Root's independent tester owns actual offline execution and any admitted PostgreSQL evidence.

Actual PostgreSQL privileges, concurrent create/replay, constraint rollback, valid verifier replay/conflict and unchanged state, controller exclusive fencing/post-wait phase recheck, and lost-connection settlement are **UNRUN in this reviewer lane**. The source provides a plausible invariant for these checks, not runtime proof. Re-review the active-list fix at a new frozen revision before approval; runtime gates remain independent.
