# T010 reset backend contract

`from eval.reset import ResetBackend, check_seed, reset_and_check`.
These are offline policy checks and a backend protocol, with no SQL adapter.
The fake backend tests are deliberately separate from actual PostgreSQL proof,
which is **UNRUN until T018**. See [oracle interface](../grading/README.md).

`check_seed(fixture, snapshot, mapping, scope, stage)` returns `Evidence`; stage
must be `before` or `after_reset`. It validates the frozen fixture, registered
run/schema/tenant identity, snapshot stage/generation and canonical seed hash.
The frozen `contracts.validate.seed_hash` helper sorts rows by declared primary
key and includes every application field, fixture/migration version and tenant.
Snapshot times and run/control metadata do not enter the business fingerprint.

`reset_and_check(backend, scope, fixture, *, receipt=None,
evidence_persisted=False)` returns `Evidence`. It supports prepared generation-0
initial reset and sealed cleanup with a matching positive fence. Cleanup requires
controller-confirmed persisted evidence. Active capabilities, unknown/quarantined
states, arbitrary schema names and wrong scope fail before reset. Reset succeeds
only on literal `True` acknowledgment, unchanged registry and a generation-matched
after-reset snapshot equal to the seed. Missing/false/nonboolean acknowledgment,
backend connection exceptions or dirty output fail; do not execute or reuse state.
Every backend call normalizes ordinary adapter/driver exceptions, including
`psycopg.Error`, into sanitized failed evidence. No raw exception text is returned.
`BaseException` interrupts/cancellation propagate for controller handling.
The implementation does not retry uncertain resets. Quarantine and evidence
persistence belong to T016; failure may require external quarantine without a DB
write. Neither this function nor the adapter marks the run `cleaned`; T016 advances
the lifecycle after the successful evidence is saved.

A backend implements these methods:

```python
read_mapping(scope: RunScope) -> dict
reset_seed(scope: RunScope, schema: str, fixture: dict) -> bool
snapshot(scope: RunScope, schema: str, stage: str) -> dict
```

The adapter must independently verify the registered run and derived schema inside
its transaction, use only the dedicated MCPBench DB and canonical synthetic seed,
and constrain each operation to 5000 ms. It must not accept a model-provided SQL
identifier, interpolate arbitrary schema names or reach another service/database.
Reset must be atomic and return True only after positive COMMIT acknowledgment.
Snapshots must be consistent read-only captures of the registered scope. The
reset operation restores application tables only and preserves the registry until
T016 records the lifecycle transition. Artifacts live outside reset scope. Final
cleanup needs revoked capabilities and positive applicable settlement; uncertain
writes must never be reset. The Python preconditions supplement, and cannot prove,
those backend guarantees. Initial setup must establish run ownership before
calling this interface.

Focused check: `python -m unittest eval.reset.test_contract -v` using the pinned
T008 environment, with bytecode disabled. Fake backend tests assert invalid scope
causes zero reset calls and failed reset cannot produce passing evidence.
