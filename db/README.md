# T011 controller database boundary

This directory contains version 1 SQL and connection-injected Python helpers for
**future isolated MCPBench PostgreSQL only**. Nothing runs on import. T011 runs no
SQL, opens no connections, and starts no containers. SQL syntax, privileges,
constraints and concurrency remain **UNRUN until T018**. Offline tests verify
Python behavior and canonical fixture agreement only.

The seven business tables match the frozen Fixture/Tables fields exactly. Control
rows and migration metadata stay in `bench_control`, outside the seed fingerprint.
The canonical synthetic corpus remains `eval/fixtures/v1/fixture.json`; there is no
second seed copy. Its fingerprint is
`8303fb14daf4ae93b75a9df9b2faa56ff9f28ab2d0c489689e9159ad848f9c78`.

## Future bootstrap and credentials

`bootstrap.sql` is a one-time bootstrap-admin script for the **new, empty, dedicated
mcpbench database**. It creates the three frozen project roles, makes the controller
DB owner, removes PUBLIC database/public-schema access, and creates control tables.
Existing project roles or control schema fail instead of silently adopting state.
It never uses existing homelab PostgreSQL or host port 5432. Database-name checks
alone cannot establish ownership: the T018 operator must verify container/project,
volume and private network identity before supplying any bootstrap connection.

Roles are LOGIN without passwords. T015/T018 must provision private passwords or
reviewed authentication using secrets; this SQL contains no credentials and does
not enable trust authentication. The controller is not SUPERUSER, CREATEROLE or
CREATEDB. No role membership is granted. The grader defaults to read-only and has
no write grants even if that session default is disabled. The service gets registry
SELECT and only `UPDATE(lock_marker)` for PostgreSQL row-lock permission, never
broad UPDATE. Application grants are SELECT on seven tables and INSERT on only
invoices, invoice_lines and idempotency_records. No sequences are needed.

## Helper interface for T018 and runner integration

Use the pinned psycopg 3.3.8 dependency already selected by T008. From the repo root:

```python
from db import manage
# conn is an idle dedicated mcpbench_controller psycopg connection, with normal
# tuple rows. The trusted runner supplies it; manage never resolves a DSN.
manage.prepare(conn, prepared_run_mapping)  # registry + migrate + seed atomically
manage.migrate(conn, run_id)               # registered prepared schema 0 -> 1
seed_hash = manage.seed(conn, run_id)       # empty or already canonical only
manage.rollback(conn, run_id)              # prepared unused schema 1 -> 0
```

`prepared_run_mapping` is the frozen full RunMapping object, prepared/generation 0
with no capabilities. `prepare` does not mint execution access. Duplicate run,
attempt or schema names fail through unique constraints, never overwrite. Each
helper owns a transaction and requires an idle connection; it refuses nested
transactions so its return cannot pretend an outer transaction committed. Use
READ COMMITTED; four-second statement and one-second lock limits are local to the
transaction. A caller must still bound the entire operation and handle uncertain
commit acknowledgment according to the lifecycle contract.

All mutation first locks the registry row FOR UPDATE and validates its full
RunMapping including the frozen `r_` + SHA256(run_id)[:32] binding. Only that stored
identifier enters driver Identifier quoting; data values are parameters. Routing
and identity columns are immutable through a registry trigger. Migration state
pins the exact up-script checksum, version, fixture version, tenant and seed hash.
A versioned reapply checks the exact table/column inventory. This is compatibility
checking, not a forensic guarantee against a privileged owner altering constraints.
Unversioned schemas and mismatched records fail; no IF NOT EXISTS adoption occurs.

Seed first checks the complete table/column inventory, rejecting extra tables or
columns before any application read or insert. It then reads back all seven
tables and verifies canonical hash before commit. A
second seed is a read-only no-op. Partial or changed data is rejected instead of
upserted or overwritten. Rollback accepts only empty/canonical unused prepared
state, leaves the immutable registry binding, drops known objects without CASCADE,
and removes migration metadata atomically. Upgrade after rollback recreates version
1 and can seed again. No later migration version is invented for this first release.
Active, sealed, cleaned and quarantined runs are rejected by these initialization
helpers. They are **not** the settled cleanup/reset API: T016 must enforce positive
fences, persisted evidence and quarantine rules before its scoped reset operation.

## Transactional invoice requirements

Money is bigint bounded by 2^53-1; quantity is 1..1000. Numeric intermediates in
checks avoid bigint multiplication/sum overflow. Foreign keys, USD/draft-only
checks, date bounds, zero tax, header/line arithmetic, unique line number/item,
unique idempotency key and one ledger binding per invoice are enforced. Deferred
constraint triggers require one to ten contiguous lines with exact header subtotal
and exactly one ledger row at transaction commit. All business fields are NOT NULL.

T012 must still validate active customers/items, fetch canonical prices, compute
amounts and normalized payload hashes server-side and insert header/lines/ledger
in one transaction. SQL deliberately cannot establish a model's trusted request,
canonical price selection or payload provenance. T012 must take the registry shared
lock before application queries; same-key conflicts and retries must follow the
frozen protocol. Service has no business UPDATE/DELETE. The controller can change
rows for scoped reset; its credentials must never reach the server or agent.

## Checks and future gated commands

Offline, using the existing T008 environment read-only (or the integrated pinned
Python environment):

```sh
PYTHONDONTWRITEBYTECODE=1 /home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python -m unittest db.tests.test_offline db.tests.test_postgres -v
PYTHONDONTWRITEBYTECODE=1 /home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python -m eval.fixtures.validate
```

After T018 admission, inside the verified dedicated private network only, bootstrap
once using a deployment-provided private admin PGPASSFILE; the fixed internal
hostname `db` must resolve to that verified MCPBench container:

```sh
PGPASSFILE=/run/secrets/pgpass-bootstrap psql -X --host=db --port=5432 --dbname=mcpbench --username=mcpbench_bootstrap --set=ON_ERROR_STOP=1 --file=db/bootstrap.sql
```

`mcpbench_bootstrap` above is the dedicated container bootstrap administrator
configured by T015/T018, not an existing host account. Provision role passwords
privately before tests. Supply a mode-0600 passfile with the three project roles:

```sh
MCPBENCH_LIVE_DB=dedicated-container PGPASSFILE=/run/secrets/pgpass-tests PYTHONDONTWRITEBYTECODE=1 python -m unittest db.tests.test_postgres -v
```

These are future commands, **not executed T011 results**. Live tests hard-code
`db:5432/mcpbench` and named project roles, overriding inherited host/database/user
settings. They create unpredictable test-only run IDs, clean only those unused
prepared schemas, and never drop a DB/volume or use global cleanup. They test
seed-twice/reconnect, rollback/upgrade, checksum rejection, FK/quantity/money and
atomic failures, missing lines/ledger at commit, valid service INSERT, idempotency
uniqueness, prohibited service writes, grader privileges and conflicting registry
locks. Real request hash replay/conflict, phase fences and grader/reset integration
remain the responsibility of T012/T016/T018–T020; these authored tests do not claim
those higher-level behaviors are implemented.
