# Dedicated PostgreSQL lifecycle adapter

`db.lifecycle.PostgresBackend` implements the frozen T016 `LifecycleBackend`.
Import and construction do not open connections. Production configuration is read
only from `/run/mcpbench/control/database.json`; there are no environment DSNs,
commands, dynamic plugins, connection pools, retries, inference or Docker actions.
Deployment ownership/network admission remains an operator prerequisite. An alias
named `db` alone does not prove container ownership.

The exact JSON object is:

```json
{
  "schema_version": 1,
  "host": "db",
  "port": 5432,
  "dbname": "mcpbench",
  "controller_passfile": "/run/mcpbench/control/controller.pgpass",
  "grader_passfile": "/run/mcpbench/control/grader.pgpass"
}
```

Extra fields, duplicate keys, alternate paths/endpoints and wrong types fail.
The control directory must be owned by the evaluator's current UID, mode0700.
Each file must be a regular, same-UID, mode0600 file; path traversal opens every
component without following symlinks. JSON is limited to 4096 bytes and each
passfile to 1024 bytes. Each role file contains exactly one scoped credential,
with an optional trailing newline:

```text
db:5432:mcpbench:mcpbench_controller:<synthetic-controller-password>
db:5432:mcpbench:mcpbench_grader:<different-synthetic-grader-password>
```

These two lines belong in their respective files, never together. Passwords
contain 16–256 ASCII letters, digits, hyphens or underscores. Wildcard hosts,
roles, databases, escaped/multiline passwords and other credentials are rejected.
Never print the actual files. `known_secrets` is a tuple containing passwords,
complete passfile lines and private conninfo strings for trusted redaction.

The production factory accepts the approved Compose environment `PGHOST=db` and
`PGDATABASE=mcpbench` (either may be absent). Any other `PG*` variable or differing
value fails before DNS, including `PGSERVICE` and `PGSERVICEFILE`. Conninfo omits
the `service` keyword: libpq interprets an empty service value as a named-service
lookup rather than disabling services. Explicit fixed connection settings remain
authoritative.
Authentication uses only the private role password. TLS/GSS are disabled for the
admitted internal project network; no external database endpoint is supported.

## Transactions, bounds and failure behavior

Each operation opens and closes a fresh connection for its own role. Controller
and grader factories are separate; connection metadata and SQL current-role/DB
checks enforce the exact dedicated database/roles. All mutating transitions lock
the registered row `FOR UPDATE` before application access, under READ COMMITTED.
The billing service must hold its frozen `FOR SHARE` registry lock through its
entire transaction. The adapter cannot make an implementation without those
service locks safe.

`set_timeout(ms)` accepts integers 1–5000. One absolute monotonic deadline covers
connection establishment, all statements, COMMIT acknowledgment and result return.
Fixed-host IPv4 DNS is performed in a bounded read-only daemon lookup; exactly one
address is required, then libpq receives that address with host `db`. There is no
address fallback. A DNS thread may finish after timeout; it can never perform SQL.
The pinned psycopg 3.3.8 connection generator and wait primitives enforce the
remaining deadline. Every query/COMMIT/ROLLBACK wait is bounded; uncertainty closes
the socket immediately without a cancellation grace period. Transaction-local
statement/lock limits provide additional server bounds. Approved `manage.prepare`
retains its local four-second/one-second limits inside the same absolute bound.
A timeout never proves remote rollback or cancellation.

Ordinary exceptions become `ContractError('lifecycle backend failed')`, without
raw connection details or exception chaining. Interrupts propagate. Any failed or
interrupted operation makes that run unavailable for every later call on this
adapter instance. Missing/late COMMIT acknowledgment never returns True or a
settled receipt, even when the remote transaction may have committed. The trusted
launcher must persist quarantine and refuse replay/reconstruction of an uncertain
attempt across evaluator processes; constructing a new adapter is not permission
to retry, reset or reuse such a run. Diagnostic operator recovery is outside this
API. There is no automatic quarantine-write retry after an unknown outcome.

## API

Call `PostgresBackend.from_private_config()` only after deployment admission.
Trusted `RunScope` and its stored schema binding select all application tables.

| Method | Behavior after timely positive acknowledgment |
| --- | --- |
| `prepare(mapping)` | Uses approved `db.manage.prepare` to register a new prepared generation-0 run, migrate and seed atomically; duplicates fail. |
| `read_mapping(scope)` | Returns validated registration through the grader connection. |
| `reset_seed(scope, schema, fixture)` | Locks registration; accepts only inactive prepared/0, agent_sealed/1 or final_sealed/2 and the frozen fixture; verifies migration/inventory, deletes only seven registered tables in FK order, seeds and verifies fingerprint in one transaction. Registry remains unchanged. |
| `snapshot(scope, schema, stage)` | Returns only the snapshot from a grader capture, rejecting schema mismatch. |
| `capture(scope, stage)` | Returns `(snapshot, mapping)` read in one grader REPEATABLE READ READ ONLY transaction. Authoritative stages require exact phase/generation; diagnostic stage has null settlement generation. |
| `activate(scope, mode, token_sha256, verification_request)` | Agent activation requires prepared/0 and no verifier request; verify requires agent_sealed/1, a draft workflow and a validated request matching the exact existing idempotency ledger. Tokens are SHA256 digests only. Expired registration fails. |
| `seal(scope, fence)` | Requires fresh executing/0 or verifying/1; acquires exclusive registry lock, revokes both capabilities and verifier scope, increments generation, commits, then creates a settled FenceReceipt with local UTC ACK observation. No replay of old fences. |
| `mark_cleaned(scope)` | Requires a sealed inactive run with canonical fingerprint and compatible migration/inventory, then changes only lifecycle state to cleaned. |

`before`, `agent_only`, and `final` captures require prepared/0, agent_sealed/1,
and final_sealed/2 respectively. `after_reset` accepts only resettable inactive
states. Cleaned/quarantined/unknown registrations are unavailable. Reads fetch at
most each Tables-contract limit plus one row (1000 generally; 10000 for timesheets
and invoice lines); excess rows fail before reset writes. Reset uses no CASCADE,
TRUNCATE, schema drop, role alteration or global cleanup.

The caller still owns oracle grading, persistence of fence/snapshot evidence
before reset, and the post-agent total budget. A database row cannot prove that
external artifacts were persisted. Those gates are enforced by T016; this adapter
does not replace them or grant an alternate recovery path.

## Offline injection and validation

For offline mocks or admitted root-owned SQL tests:

```python
backend = PostgresBackend(
    controller_factory=controller_factory,
    grader_factory=grader_factory,
    known_secrets=(),
)
```

Each factory receives one absolute `time.monotonic()` deadline and must return a
fresh idle tuple-row connection with the role's exact identity. It must bound
connection creation and every driver wait, including commit/rollback, to that
same deadline. The injectable monotonic clock is for deterministic unit tests.
Factories are trusted Python callables, never loaded from runtime configuration.
For an admitted host-side test, `host='db', hostaddr=<verified-owned-container-IP>`
retains the fixed metadata identity without requiring host DNS changes. Ordinary
unbounded psycopg connections are not a production substitute for the deadline
connection implementation.

Offline command (no SQL connections):

```sh
PYTHONDONTWRITEBYTECODE=1 /home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python -m unittest db.tests.test_lifecycle db.tests.test_offline -q
```

These tests prove Python behavior using mock connections, including unknown/late
ACK handling, no retry/reuse, role separation, consistent capture, revocation,
scoped reset and configuration checks. Actual SQL semantics, privileges, locks,
rollback and positive-ACK timing are **UNRUN by this implementation worker**.
The root operator owns admitted live PostgreSQL evidence and independent review.
