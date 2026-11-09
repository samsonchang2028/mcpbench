# T016 private evaluator lifecycle

`Evaluator(Artifacts(private_run_root), backend).invoke(control_request)` executes
one frozen `ControlRequest` phase and persists a matching `ControlResult`. It
starts no agent, verifier, subprocess, Docker operation or model request. The
trusted host launcher executes children, supplies their `ProcessExit` records and
enforces process deadlines. This module uses only the full-context agent request.

The CLI accepts exactly `python -m eval.runner prepare`, `settle-grade` or
`finalize`. It reads the bounded, owner-only mode0600 regular JSON file at
`/run/mcpbench/control/request.json` without following symlinks in the file or its
ancestors. Its lazy fixed `db.lifecycle.PostgresBackend` import loads private DB
configuration from `/run/mcpbench/control/database.json`. There is no environment
DSN lookup, arbitrary executable argument or configurable plugin import.

The trusted launcher prepopulates all relative input references under the separate
mode0700 `/run/mcpbench/output` writable mount. That mount must be private to the
evaluator; never expose its parent or oracle/private files to a child. Artifact
references retain the frozen 2–4-segment relative-path contract and exact byte/hash
binding. Results are published as `control/<phase>-result.json` there; the host
validates and copies the exact phase result bytes to its fixed private
`/run/mcpbench/control/result.json` transport before recording evaluator delivery.
This copy/mount integration is T019 work, not proof supplied by offline tests.

## Ordering and safety

* Prepare validates the immutable task/fixture and registered run, performs a
  scoped acknowledged reset and seed check, saves the before snapshot, then
  publishes sanitized `AgentRequest` and a separate private `AuthInput`. Failed
  reset blocks execution. Backend activation must positively acknowledge commit.
* Settle-grade requires a reaped agent and an acknowledged registry fence before
  taking an agent-only consistent capture. Independent oracle and answer checks,
  host process outcome, task budgets and captured traces determine the original
  verdict. Only an original passing draft can receive the two-call verifier
  capability. Read-only and failed originals bypass verification.
* Finalize checks verifier delivery and the second fence when applicable, captures
  final state, preserves the original verdict, checks replay and unchanged state,
  saves evidence and its hash manifest, then resets only the settled registered
  scope and checks its seed. Cleanup failure quarantines and prevents reuse.

Missing/stale references, lost acknowledgments, unreaped children, expired budgets
and unknown settlement fail closed. An uncertain phase preserves a separate
quarantine evaluation when enough original context is available; it never resets
potentially live writes. Immutable phase-invocation markers reject repeated phase
execution. The launcher must quarantine on evaluator transport/publication failure
or restart rather than retrying with a fresh post-agent clock.

`Budget` preserves the single launcher anchor and elapsed observations across
phases. The total post-agent budget is 30 seconds, including transport and startup;
each backend operation gets at most the remaining budget or five seconds. The
absolute UTC deadline also bounds remaining time before expiry, charging stale
startup/transport observations conservatively. Each resulting elapsed floor then
advances with local monotonic deltas; backward UTC changes cannot restore time.
Elapsed milliseconds round upward so submillisecond expiry grants no new IO.
These UTC floors are safety-budget observations, not cross-producer latency
measurements. Backend deadlines must include connection, lock, statement
and commit acknowledgment. The Python timer alone cannot cancel a blocked driver.

## Backend and artifacts

`LifecycleBackend` in `lifecycle.py` defines the adapter methods shared with T018:
`set_timeout`, `prepare`, `read_mapping`, `reset_seed`, `snapshot`, `capture`,
`activate`, `seal`, `mark_cleaned`. `capture` returns snapshot and registry from
one read-only grader transaction. `seal` must hold the exclusive registry lock
through committed capability revocation, matching the service transaction's shared
lock. Reset and transition success require literal `True`. `known_secrets` is an
optional tuple of all private passwords/DSNs for public-artifact redaction.

Artifact publication uses mode0600 temporary files, file/directory fsync and an
atomic no-replace link. Existing results are never overwritten. File consumption
rejects symlinks, nonregular files, permissive modes, invalid JSON and byte/hash
mismatches. Per-record JSON is capped at 1 MiB and the run at 100 MiB. Evaluator
events are durable separate JSONL records with one persisted source sequence;
captured child streams receive strict complete-stream validation. Incomplete
traces invalidate comparison independently of the original task verdict.

Private auth/state files contain evaluator-only secrets and oracle data. Public
artifacts redact capability literals/digests and backend-known secrets; backend
exceptions become fixed failure categories. The hash manifests cover immutable
bytes, including private files, and exclude only their own bytes. Missing metrics
remain null with reasons in `evidence/metrics-availability.json`; live costs,
energy and cross-process latency are not fabricated.

## Checks and remaining proof

From this checkout with the existing pinned environment, without installs:

```sh
PYTHONDONTWRITEBYTECODE=1 /home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python -m unittest eval.runner.test_lifecycle eval.runner.test_artifacts -q
```

These checks use a scripted backend and prewritten child evidence only. They
exercise three-phase invoice/read-only behavior, original-failure preservation,
timeout, reset/cleanup failures, stale/missing evidence, unknown fences, CLI fixed
loading, redaction, path integrity, file bounds and nonblocking FIFO rejection.
Real PostgreSQL grants/transactions/late commits, mounts, runtime telemetry,
launcher transport and live model execution remain **UNRUN** in T016. T018/T019
must establish those under their own gates; fake ACKs do not prove SQL fencing.
