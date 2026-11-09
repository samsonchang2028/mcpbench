# T019 trusted deterministic launcher

This host-only launcher joins the existing evaluator, agent loop, official MCP
SDK and dedicated PostgreSQL lifecycle. The integration image replaces only the
model with a deterministic script; it never contacts native Ollama. Production
`cmd/agent` is unchanged. Scripted tag/source digest, frozen image IDs and the
`native_inference:false` marker identify the evidence honestly.

`python -m launcher --config /absolute/private/launch.json` accepts a trusted,
same-UID mode0600 JSON file beneath a mode0700, symlink-free private directory:

```json
{
  "schema_version": 1,
  "images": {
    "agent": "sha256:<64 lowercase hex characters of the scripted image ID>",
    "mcp": "sha256:<64 lowercase hex characters of the MCP image ID>",
    "evaluator": "sha256:<64 lowercase hex characters of the evaluator image ID>"
  },
  "service_passfile": "/absolute/private/service.pgpass",
  "control_source": "/absolute/private/evaluator-control-template",
  "artifacts_parent": "/absolute/private/t019-runs",
  "scenario": "smoke"
}
```

The image ID placeholders above are explanatory, not valid runnable values. The
operator must inspect the admitted builds and supply their actual reviewed IDs.
No tag, arbitrary command, backend module, endpoint or model-supplied path is
accepted. `scenario` is `smoke`, `wrong-write`, or `lost-reply` and must match the
scripted image's build argument. The artifact parent must already be owned by the
launcher UID with mode0700. The service passfile is same-UID mode0600. The control
source contains only the approved private `database.json`, `controller.pgpass`
and `grader.pgpass` inputs described in `db/LIFECYCLE.md`, each mode0600. Actual
password bytes stay in these private files; never put them in launch JSON or
command arguments. The operator verifies DB CID/network ownership, free18081,
image identities, host UID1000 and the normal resource gate before invocation.

The launcher creates unpredictable run/attempt/key IDs, a derived registered
schema, fixed smoke task/fixture inputs and a 300-second maximum registration.
Each new run directory and its fsynced entered.json are an exclusive restart
barrier; absence of a validated complete.json means incomplete/quarantined even
if a full filesystem prevents a later diagnostic publication. Existing attempts,
including interrupted or quarantined attempts, cannot be retried or reused.
It executes prepare → agent → settle-grade → optional verifier → finalize, using
only fixed commands and narrow mounts. Evaluator result bytes are validated,
hashed, copied exactly to fixed control/result.json and retained immutably in the
journal. Each actual child has a typed ProcessExit with observed exit/reaping and
delivery status; the final ControlChain gets authoritative validation.

One monotonic post-agent anchor starts at the observed agent exit/deadline.
Transport, container startup and all later work consume the same 30 seconds;
post-agent evaluator/verifier children also get at most five seconds. There is no
resetting of that clock across phases. A bounded Docker operation that cannot
positively prove its outcome forces quarantine. No failure restarts a child or
resets/reuses an uncertain run. Exact fresh container IDs are persisted before
attach; cancellation/removal is always restricted to those IDs, without volume
flags. On quarantine, preserve those receipts and resources for operator fencing
and diagnosis. The launcher never attempts speculative reset or cleanup then.

The operator must retain all run files, including stderr and journal/quarantine
records. Only original settled evidence can permit replay, and only persisted
settlement/verification can permit reset. Missing original trace data still goes
to settle-grade for its first fence, then forces launcher quarantine. Missing or
invalid verifier evidence blocks finalize/reset. Quarantine is an incomplete run,
never a passing substitute for live evidence.

Raw execution-agent and verifier-agent streams remain separate because each
process starts its agent source sequence at1. The MCP writer spans both phases
with one sequence and local clock. Original agent+MCP snapshot streams are
validated together; verifier-agent and final full MCP streams are independently
validated before finalize. No source IDs/sequences/timestamps are renumbered.
All raw bytes and hashes retain their actual provenance. Verifier budget/call
counts remain in its own result and ProcessExit. Aggregate artifacts across every
mount/journal/log are monitored against100MiB; per-document/trace copy bounds fail
closed. The hard bounds may reject an unusually large trace rather than truncate
or fabricate records. A host filesystem quota remains useful defense against a
misbehaving child; polling is not claimed as a kernel disk quota.

## Operator commands — runtime gated and unrun by source author

After fresh admission and independent source review, build sequentially with the
operator's admitted CPU/memory flags. These commands select frozen base references
already pinned in the Dockerfiles; the operator records actual output image IDs:

```sh
docker build --target mcp -f containers/go.Dockerfile -t mcpbench-mcp:t019 .
docker build --target scripted-agent --build-arg MCPBENCH_SCRIPTED_SCENARIO=smoke -f containers/go.Dockerfile -t mcpbench-scripted-agent:smoke-t019 .
docker build -f containers/evaluator.Dockerfile -t mcpbench-evaluator:t019 .
```

Use the same scripted target with `wrong-write` or `lost-reply` for their separate
images/configs/attempts. The trusted driver starts a fresh MCP service on only
`127.0.0.1:18081`, verifies its real `/healthz`, and launches serial one-shot
children from exact image IDs. It never starts/reconfigures native Ollama or the
existing owned DB. Run from this reviewed checkout with the cached Python:

```sh
PYTHONDONTWRITEBYTECODE=1 /home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python -m launcher --config /absolute/private/launch.json
```

Expected assertions: smoke original PASS,25000-cent draft, real verifier replay
and conflict, unchanged final state, and exact seed restoration. Wrong-write
produces37500 cents and must retain original FAIL with no verifier, then a safe
seed reset. Lost-reply discards a real committed reply at the agent adapter,
retries the original key/payload once and must preserve the invoice. It is an
explicit response-loss fault, not a claim of a naturally occurring network outage.
The CLI checks expected original outcome and comparison validity; evaluator
snapshot/oracle/replay/reset evidence supplies the substantive database proof.

The additional opt-in SDK regression checks require an independently prepared,
fresh execution capability for each case, an admitted real MCP service and the
normal operation gate. They never prepare/reset/drop a run themselves:

```sh
MCPBENCH_INTEGRATION_LIVE=yes MCPBENCH_INTEGRATION_AUTH=/absolute/private/auth.json GOMAXPROCS=1 GOTOOLCHAIN=local GOPROXY=off go test -mod=readonly -p=1 -count=1 -run '^TestConcurrentDuplicate$' ./tests/integration
MCPBENCH_INTEGRATION_LIVE=yes MCPBENCH_INTEGRATION_AUTH=/absolute/private/other-auth.json GOMAXPROCS=1 GOTOOLCHAIN=local GOPROXY=off go test -mod=readonly -p=1 -count=1 -run '^TestTimeoutAfterCommittedResponse$' ./tests/integration
```

These assert matching real server invoice IDs, canonical25000 cents, and exactly
one injected client timeout after a positively acknowledged server reply. Root
must independently capture/seal each run through the approved Python backend,
assert exactly one invoice/ledger plus one canonical line of quantity2, and prove seed reset.
They are separate regression attempts, not unrecorded extra calls in the smoke
agent's comparison budget. Without explicit admission, both tests report SKIP.

## Source evidence

Cached single-core Go and pinned Python checks exercise the actual loopback SDK,
strict Event/stream parity, application SQL hooks via test transactions, secret
updates, causal ControlChain timing, typed phase transport/mounts, restart and
unknown-fence quarantine, missing traces and aggregate quota. Python launcher
unit tests use scripted backend/child evidence; they are explicitly not live SQL
or actual process/reaping evidence. Docker/static rendering, builds, actual
container launches, live regression cases and actual full-stack proof remain
operator-owned and UNRUN by this source worker. No inference was performed.
