# T012 PGX store

The store uses only the pinned pgx v5.11.0 package and an injected connection
source. Both `session_user` and `current_user` must be `mcpbench_service`, in
`mcpbench`. A controller connection with SET ROLE is rejected. Production connection
configuration and credentials belong to the trusted deployment adapter, never
model arguments. Connections must not be concurrently reused directly.

Every transaction is READ COMMITTED, with local statement (4s) and lock (1s)
timeouts inside the overall 5s operation deadline. After checking role/database,
the first control/application lock is the run registry row `FOR SHARE`. Only then
are the latest capability digest (constant-time compare), phase, generation,
expiry, principal, allowed tools, workflow and immutable run/schema mapping checked.
The stored schema must match `r_ + SHA256(run_id)[:32]`; pgx identifier quoting
handles this validated registry value. All data values use SQL parameters.
The shared registry lock is held through COMMIT or rollback acknowledgment.

Execution create calls then take a transaction-scoped PostgreSQL advisory lock of
`hashtextextended(run_id + ':' + trusted_key, 0)`. Requests in the same run with
that key serialize before reading the ledger. READ COMMITTED ensures the waiter
sees the committed first result. Hash collisions only serialize unrelated work;
lookup remains scoped by registered schema and full key. Invoice header, ordered
lines and ledger INSERTs share the same transaction, with deferred DB constraints
from T011. No UPDATE, DELETE, sequence, registry mutation or reset is issued.
The SQL/grant/concurrency behavior remains subject to actual T018 admission.

## Authored PostgreSQL checks: UNRUN

`postgres_test.go` is opt-in with `MCPBENCH_LIVE_DB=dedicated-container` and a
private project `PGPASSFILE`. It hardcodes `db:5432/mcpbench` and service login,
never a host DB or controller credential. No live check has been executed in T012.
The owned T018/T019 harness must create distinct unused runs, supply canonical
fixture data and lifecycle state, and retain evidence and perform fenced cleanup.
The tests themselves never bootstrap, create runs, mint tokens or clean/reset.

Each following environment variable names a regular mode-0600 private JSON file
containing `billing.Access` fields (`RunID`, `AttemptID`, `IdempotencyKey`,
`Capability`). The controller must ensure the run is exclusive to its test:

- `MCPBENCH_T012_EXECUTION_ACCESS`: executing/generation 0, canonical empty fixture,
  three-tool drafter ACL, live execution token. Two independent service connections
  concurrently create the same draft, return one ID and 25000 cents, then reject
  changed quantity and assert exactly one header/line/ledger persisted.
- `MCPBENCH_T012_INVALID_ACCESS`: separate equivalent executing run. A request with
  one valid then one missing item must leave all three write tables empty.
- `MCPBENCH_T012_MISSING_VERIFIER_ACCESS`: verifying/generation 1 with execution
  digest revoked, verifier scope/key/hash bound to the canonical request but no
  saved ledger. Request must return `verification_not_replayable`.

Run after independent resource/connectivity and project-ownership admission:

```sh
MCPBENCH_LIVE_DB=dedicated-container PGPASSFILE=/run/secrets/pgpass-tests GOMAXPROCS=1 GOTOOLCHAIN=local GOPROXY=off go test -mod=readonly -p=1 ./internal/store -run Postgres -v
```

The harness supplies the corresponding private access-file variables. Missing
inputs skip explicitly; skipped checks are UNRUN, never runtime PASS. Actual
service privilege denial, deferred-constraint rollback, controller FOR UPDATE
fencing, post-wait phase recheck, lost-connection settlement and final independent
snapshot equivalence require owned T018–T020 integration. Offline fake transaction
checks cannot establish any of those properties.
