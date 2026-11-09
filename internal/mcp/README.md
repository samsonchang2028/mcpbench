# T013 billing MCP transport

`New(Options)` serves the official Go SDK **v1.8.0** Streamable HTTP transport at
`/mcp`, with stateless sessions, JSON responses and request cancellation. The real
SDK negotiates **2026-07-28** using `server/discover`; initialize is the SDK's
legacy compatibility path. Only the three frozen smoke tools are registered.
Their complete input and business output schemas expand the embedded frozen
catalog/schema references. `StructuredContent` is the business output on success,
and a direct bounded `ToolError` with `IsError=true` on failure. Unknown direct
tools/methods and malformed JSON-RPC retain SDK protocol errors.

The HTTP guard checks exact Host/Origin allowlists, duplicate private headers,
64-lowercase-hex Bearer capabilities and bounded identifiers. Every `/mcp` request
calls `Service.Authorize` afresh, including discovery, list, unsupported methods,
GET/DELETE and malformed bodies. List filtering uses that request's ACL; the
billing `Service.Call` authenticates again inside its locked transaction. Access
never comes from model arguments. Health is a separate non-sensitive GET endpoint.
Only health permits container-local `localhost:8080`/`127.0.0.1:8080`; MCP Host is
`localhost:18081`/`127.0.0.1:18081`. Origin is absent/empty or the two frozen HTTP
origins on port 18081. Bodies and buffered JSON-RPC responses are capped at 1 MiB.
Strict UTF-8, duplicate keys, trailing JSON and nesting failures are handed to the
SDK as malformed JSON rather than admitted through its general JSON decoder.

The adapter reuses the existing agent's pure strict JSON, argument and business
result validators. These functions do not make network calls or execute Python.
Its own cached compiled frozen schema validates the emitted MCP event subset.
Embedded contract identity tests detect drift from `contracts/v1/`.

## Production command and readiness

Build/run the repository command `./cmd/billing-mcp` with no arguments; it listens
on **:8080** for the existing Compose loopback publication. It requires only the
approved dedicated configuration: host `db`, port `5432`, database `mcpbench`,
user `mcpbench_service`, password file `/run/secrets/service.pgpass`. Matching
`PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSFILE` environment settings are
allowed; mismatching or other `PG*` overrides are rejected. Credentials and raw
connection failures never reach stderr or public errors. No DSN/config mount or
additional dependency is needed.

`ServiceSource` uses at most **five fresh, unpooled connections**. Slot acquisition,
connect, transaction and close use the caller's five-second operation context.
A wrapper releases the connection exactly once after COMMIT/rollback; no connection
is shared concurrently. There are no background connections or internal retries.
The command checks readiness before listening. GET `/healthz` rechecks the real
service login/current role/database and access to every required control registry
column; database/control-schema failures return 503. This is service readiness,
not proof of a particular run's migrated/seeded application schema. The evaluator
must still establish that run's seed fingerprint before execution. Readiness does
not use a fake success callback in production.

## T019 integration obligations

The injected service and readiness APIs permit owned-loopback SDK tests without
opening PostgreSQL. Production uses `billing.Service{Repo:store.New(source)}`.
No Compose/launcher/config changes are part of T013. T019 must enable an actual
health check using GET `/healthz` at `http://127.0.0.1:8080` inside the container.

`Options.Events(runID, attemptID)` must resolve a trusted, existing run-specific
`observability.Writer` and the current `execution`/`verification` phase. Create
writers with `Source:"mcp"`, `Validate: mcp.ValidateEvent`, and private secret
redaction; close them at the trusted lifecycle boundary. The launcher must provide
narrow MCP trace mounts/routing and retain the resulting files in the assembled
trace. The default standalone command currently has **no trace factory**, so it
cannot claim complete benchmark evidence. Successful argument validation precedes
emission; each dispatched call emits paired tool start/terminal events. The MCP
adapter performs no internal retry, so its own retry index is zero. Agent retry
attribution remains in the agent trace.

The private `Diagnostic(runID, attemptID, outcomeUnknown)` callback preserves an
unknown transaction outcome without asserting rollback/commit. Production emits
only the fixed `settlement_unknown` category and bounded run/attempt identifiers
on private service stderr; T019 must retain that stderr with settlement diagnostics.
Public ToolError messages are bounded categories. No capability/digest is logged.

Actual `db.started`/terminal events require hooks at the real billing/store
transaction boundary. T013 emits tool events only: it cannot infer a transaction
ID, read/create/replay branch, positive COMMIT acknowledgment or rollback from
an opaque Service invocation. T019 owns that shared telemetry seam. The server's
private unknown-outcome callback supplements settlement evidence; it never proves
that a write settled. Missing trace wiring remains an integration obligation.

## Author evidence

On 2026-11-08, with Go 1.26.8, cached dependencies and the existing T008 Python:

```sh
MCPBENCH_TEST_PYTHON=/home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python \
GOMAXPROCS=1 GOTOOLCHAIN=local GOPROXY=off \
go test -mod=readonly -p=1 -count=1 ./internal/mcp ./cmd/billing-mcp
```

**PASS**: real SDK loopback discovery/version negotiation, exact resolved schemas,
ACL-filtered catalog, fresh authorization/revocation, calls, invalid arguments,
unknown direct tools, invalid business results, direct bounded errors, unknown
commit diagnostics, secret exclusion, Host/Origin/duplicate-header/UTF-8/duplicate
JSON/body bounds, unhealthy readiness, response cap, cancellation-aware connection
slot acquisition, environment rejection, and real durable writer events checked
by the authoritative Python Event and complete-stream validators.

These are transport/test-double checks. Real dedicated PostgreSQL connections,
service grants, concurrent/fenced database writes, container startup/health,
launcher-mounted traces and live model inference remain **UNRUN** in T013.
The same environment with `go test -mod=readonly -p=1 -count=1 ./...` also
**PASS** across all Go packages; opt-in database tests remain skipped/unrun.
Independent reviewer/tester acceptance is separate from author evidence.

## T019 source join

The command now installs a trusted `TraceFiles` factory from the separate RO
`/run/mcpbench/trace/config.json` and RW `/run/mcpbench/events` mounts. The config
has exact fields `schema_version`, `run_id`, `attempt_id`, `phase`, `secrets`;
phase advances from execution to verification, identity never changes, secrets
are a cumulative list of the one/two private capability literals. It is owner-only
mode0600, strict JSON and symlink-free. `Writer.AddSecrets` installs verifier
redaction before requests proceed, preserving the same MCP source sequence.

Store instrumentation starts spans at actual application SQL boundaries, not
around an opaque Service call. Each actual transaction shares a generated private
transaction correlation ID; all of its SQL spans finish only after its real
COMMIT/rollback outcome. Missing ACK emits uncertain `settlement_unknown`, never
`db.completed`. Rows affected stay null rather than inventing counts. Frozen
semantics label execution reads (including duplicate lookup) `read_tool`, writes
`create_draft`, and verifier SQL `replay`. Registry-only auth emits no application
DB span. The genuine validator now supports these DB events and phase constraints.

`billing-mcp health` checks the real fixed local HTTP health endpoint; Compose
uses it as its health command. Graceful termination closes the durable trace and
propagates close failure. See `launcher/README.md` for exact runtime ownership,
scripted evidence limits, per-run mount routing and quarantine handling. Earlier
T013 UNRUN statements remain historical author evidence, not a T019 live claim.
