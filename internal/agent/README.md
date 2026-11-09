# T014 full-context execution agent

`cmd/agent` implements the frozen file entrypoints:

```
/app/agent run --request /run/mcpbench/request.json --auth /run/secrets/auth.json --output /run/mcpbench/output
/app/agent verify --request /run/mcpbench/request.json --auth /run/secrets/auth.json --output /run/mcpbench/output
```

The launcher supplies a fresh, isolated output directory and separate typed
request/auth files. Stdout stays empty; failure stderr is one fixed category.
The agent rejects duplicate JSON keys, unknown contract fields, invalid Unicode,
oversized documents, symlinks and preexisting artifacts. It publishes a fsynced
result using an exclusive atomic hard link; partial event files remain evidence
of failure. The launcher still owns mount/ancestor isolation and validation of
complete result delivery, deadlines and process exit.

The loop exposes all authorized tools in the three-tool smoke catalog. It uses
native Ollama `/api/chat`, `stream:false`, request-local settings and the fixed
loopback endpoint. No model is pulled, unloaded, replaced or reconfigured.
Unknown names, denied create attempts and invalid raw arguments consume the tool
budget without dispatch. Locally generated IDs correlate assistant selections
with tool messages. Capability and idempotency metadata enter only trusted MCP
HTTP headers; known secrets are redacted from events and answers. Draft IDs and
invoice amounts come from validated server results; the model never supplies
trusted totals. The first slice returns the saved invoice ID; general read-only
answer extraction remains outside this draft-invoice lane.

Pinned SDK v1.8.0 defaults to selected protocol **2026-07-28**. Cached upstream
source `mcp/client.go` (`Client.Connect`) implements `server/discover` negotiation
before `tools/list` and `tools/call`; this is the selected protocol handshake.
The owned fake transport test exercises that path, without a real service.
The client advertises no roots/sampling capabilities. It disables proxies,
redirects, standalone SSE and automatic transport retries. The MCP server must
select JSON responses with business output in `structuredContent`
(or one text JSON block); error responses carry the bounded `ToolError`. The
client normalizes the known request tool ID and SDK `isError` bit into its
validated internal frozen `ToolResult`. Raw duplicate keys are rejected before SDK decoding.
SSE responses fail closed in this bounded JSON transport profile.

Task/model/tool budgets never extend the caller deadline. The context guard
conservatively charges one token per serialized UTF-8 byte plus output allowance;
it may reject requests that a model tokenizer would fit, and never truncates.
Actual returned token counts are retained and checked. At most one transient
retry consumes the same task/call budgets, unchanged arguments and the same
trusted idempotency key. Model calls are never retried.

Verify mode performs only same-payload replay and the constrained changed-quantity
conflict call. It invokes no model/discovery, never retries, and uses the smaller
of the remaining absolute deadline and supplied remaining budget. A single
monotonic observation starts at CLI entry, charges MCP startup, and caps startup
and each call at five seconds or the remaining budget, whichever is smaller.
Expected conflicts retain typed error responses as recovered idempotency-conflict
evidence; failed checks retain terminal verification failures. It reports typed evidence; it cannot establish SQL settlement,
repair an original failure or grant a fresh post-agent budget.

Events use `observability.Writer` with a real schema plus semantic validator for
the emitted subset. The embedded `schema.json` is an exact copy of the frozen
v1 schema, with no contract changes. Unsupported event kinds fail closed.
Python parity checks validate emitted complete traces and adversarial nested
semantics, including calendar dates, UTC timestamps and invoice date order, with
the authoritative contract validator. Runtime starts no Python
process. T019 owns combined producer wiring and real MCP/database integration;
T021 owns aggregate metrics/fairness acceptance.

Run deterministic checks from this worktree with the existing pinned environment:

```
MCPBENCH_TEST_PYTHON=/home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python GOMAXPROCS=1 GOTOOLCHAIN=local GOPROXY=off go test -mod=readonly -p 1 ./internal/agent ./internal/ollama ./cmd/agent -count=1
```

Tests use scripted model/tool interfaces and owned fake HTTP transports. Live
Ollama, MCP, SQL, containers, image builds and model smoke tests remain UNRUN;
these deterministic results make no live benchmark claim.
