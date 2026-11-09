# T019 independent tester — frozen source candidate

Date: 2026-11-08. Route: FULL. Source-check verdict: **PASS** for the requested cached offline/fake-loopback scope. Full T019 acceptance remains **BLOCKED pending operator-owned live evidence**; the live criteria below are **UNRUN by this tester**. Unit/scripted success does not mark T019 DONE.

Candidate: `a85d9f9b4400b3731736447230bea74d7f993674`, parent `90e0df094765305ededc915101033211b713f083`, checkout `/home/sfkim/projects/mcpbench/.worktrees/T019`. HEAD matched assignment; worktree was clean before and after checks. No source/test changes were made. This report is the only file written by this tester.

Read main AGENTS.md, tester/task-classifier instructions, latest main T019 context pack and TASK_GRAPH acceptance row, relevant EVALUATION_PLAN lifecycle/oracle/trace/validation sections, candidate launcher/README.md, contracts/README.md, eval/runner/README.md and containers/README.md. Applied token-efficient-coding. No installs, builds, container launches, SQL connections, models, native configuration changes or daemon inspection were performed. Compose rendering uses synthetic absent mount paths and does not contact the daemon.

## Commands and actual results

All commands below ran in the candidate checkout. Tool sessions were polled to completion, never restarted.

```sh
MCPBENCH_TEST_PYTHON=/home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python GOMAXPROCS=1 GOTOOLCHAIN=local GOPROXY=off go test -mod=readonly -p=1 -count=1 ./...
```

**PASS**, exit 0. Session `4646`, initial chunk `d3b5c0`, completion chunk `95d8fb`. Actual package results: cmd/agent 0.864s; internal/agent 2.992s; internal/billing 0.129s; internal/mcp 0.708s; internal/ollama 0.007s; internal/store 0.006s; observability 3.589s; tests/integration 0.004s. cmd/billing-mcp and tests/integration/scripted-agent have no test files. The two opt-in integration tests skip before auth loading or endpoint access unless explicit live admission is set; package success does not prove those live cases ran.

```sh
PYTHONDONTWRITEBYTECODE=1 /home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python -m unittest launcher.test_run contracts.tests.test_contracts eval.runner.test_lifecycle eval.runner.test_artifacts -v
```

**PASS**, exit 0, `Ran 91 tests in 11.143s`, `OK`. Session `40673`, initial chunk `dc381d`, completion chunk `bc4d93`. Count includes imported/inherited lifecycle test invocations, not 91 distinct scenarios. Expected fixed CLI negative-test stderr was `mcpbench: expected fixed evaluator phase` and its test passed.

```sh
PYTHONDONTWRITEBYTECODE=1 /home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python containers/check_config.py
env -i PATH="$PATH" docker compose --env-file /dev/null -p mcpbench -f compose.yaml --profile '*' config --quiet
```

**PASS**, exit 0 for each; chunks `ddb062` and `3d862c`. Static checker reported: `PASS: Compose render; 5 identities/limits; private DB; loopback MCP; separate narrow agent/verifier mounts; pinned bases; no daemon/runtime operations`. Quiet render emitted no output. No rendered credential contents were printed.

Observed toolchains: Go `go1.26.8 linux/amd64`, pinned Python `3.14.4`. Candidate pins official MCP SDK `v1.8.0`, pgx `v5.11.0`; no dependency or model selection changed.

## Criterion mapping and coverage limits

| Criterion | Source result / observed evidence | Remaining proof |
| --- | --- | --- |
| Increasing causal budgets, one anchor, no regression | PASS: `test_control_chain_observations_follow_generation_order` accepts request20 → generated verifier request25 → settle result30 → exit35 → verifier40 → exit45 → finalize50/55/60ms; rejects generated request19/31, verifier34, restarted anchor and changed deadline. Shared-deadline and evaluator deadline tests also pass. | Actual process/container startup and transport charged against this bound: UNRUN. |
| AddSecrets atomic validity, copy, close/failure, redaction and stream continuity | PASS: new literal redacts at sequence2 without reset; caller mutation cannot replace it; mixed valid/empty update has no partial effect; invalid UTF-8, closed and failed writers reject updates. MCP phase-continuity test installs newly minted capability before admission and rejects phase rollback/foreign run. | No dedicated concurrent AddSecrets test or race-detector run exists in this executed scope. Static inspection shows AddSecrets, Emit and Close use the same writer mutex; thread safety is source evidence, not a concurrent stress-test result. |
| Trusted mounts and credentials | PASS: launcher fixed-command test rejects arbitrary phases/images and checks three agent mounts, no evaluator/control mount and hardened command. Static Compose checker verifies exact separate agent/verifier mounts, sanitized environment, private DB, loopback18081, fixed health command, limits and pinned bases. Redaction/artifact tests pass. | Actual mount isolation and absence of credentials in real child outputs: UNRUN. |
| Aggregate quota and durable quarantine | PASS: launcher rejects aggregate size above100MiB; transport failure/unknown agent fence never finalize/reset/retry; missing original trace still triggers initial settlement before quarantine; invalid verifier trace prevents finalize/reset. | Real child output growth, filesystem full behavior and daemon uncertainty: UNRUN. Polling is not a kernel quota. |
| Restart barrier | PASS: exclusive existing attempt is rejected after both complete and transport-failed attempts; entered/quarantine evidence is durable by source design. | A newly constructed launcher after actual host/process interruption was not exercised; live restart recovery/fencing: UNRUN. |
| Typed ProcessExit, result transport, trace provenance | PASS at scripted/contract level: complete chain has five exits, exact finalize-result transport bytes, five-second post-agent child caps; malformed/missing/partial delivery and unreaped evidence are rejected. Original and verifier agent streams remain separate; full MCP stream parity checks pass. | Actual Docker child exit, inspection/reaping, receipts, attached process completion and deadline handling: UNRUN. Scripted Outcome is not live process proof. |
| DB transaction telemetry | PASS: mocked transaction tests require terminal emission after commit/rollback acknowledgment and preserve unknown outcomes; logging-start failure prevents application operation. Go/Python full-event parity passes. | Real PostgreSQL transaction-boundary trace join: UNRUN. |
| Canonical invoice/oracle, wrong writes, seed reset | PASS only with scripted backend and existing billing/oracle checks; no observed source-check defect. | Real PostgreSQL + official MCP + scripted child producing exact25000-cent draft, wrong37500-cent persisted write rejection, independent snapshots and exact seed hash restoration: UNRUN. |
| Replay, concurrent duplicates, committed-response timeout | Existing source checks PASS; opt-in SDK checks require explicit admission and correctly skip by default. README requires independent row/ledger/line counts and reset. | Real verifier same-key replay/changed-payload conflict with unchanged state, concurrent duplicate exactly one invoice/ledger/line, and lost committed reply retry retaining original invoice: UNRUN. |

No observed P0/P1 source-test failure was found in this scope. Coverage limitations above are explicit; they are not evidence that the unrun behavior works. Root owns refreshed resource admission, independent review, live scenarios, durable runtime artifacts and the task-status decision. Scripted tests establish neither real PostgreSQL settlement nor Qwen tool support.
