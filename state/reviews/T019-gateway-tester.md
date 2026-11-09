# T019 gateway independent verification

Candidate: `53c62bdbb70f08455a8da9c643c626bcbe8909fc`, base `c97f44e`, clean frozen worktree `/home/sfkim/projects/mcpbench/.worktrees/T019`. Verified 2026-11-09. Read main AGENTS.md, tester role, approved-A context and main architecture, evaluation plan, candidate tests and runtime READMEs. FULL route applies to the network/security boundary. No source edits or tests added; only this report was written in main.

**Current required source gate: PASS for corrected candidate `5c3dd4aa7550e3fc1632f455575cb9e5ff60fbc6`.** The original `53c62bd` checker failure and its actual evidence are retained below. The focused correction passes independent regression tests and actual sanitized rendering/checking. Runtime acceptance remains **UNRUN**, so this report does not establish T019 DONE.

## Corrected-candidate recheck

Independently verified clean HEAD `5c3dd4aa7550e3fc1632f455575cb9e5ff60fbc6`. `git diff --name-only 53c62bdbb70f08455a8da9c643c626bcbe8909fc..5c3dd4aa7550e3fc1632f455575cb9e5ff60fbc6` reports only `containers/check_config.py` and new `containers/test_check_config.py`. The prior Go,98 Python, SDK gateway and inline negative results therefore apply to unchanged implementation files; they were not rerun or misrepresented as new runs.

All three focused checks ran in the frozen T019 worktree with the same pinned Python and sanitized rendering environment:

| Command | Actual result / execution handle |
| --- | --- |
| `PYTHONDONTWRITEBYTECODE=1 /home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python -m unittest containers.test_check_config -v` | PASS exit0, three tests in0.001s, chunk74d0a3. |
| `PYTHONDONTWRITEBYTECODE=1 /home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python containers/check_config.py` | PASS exit0, chunk29d2eb: full checker reaches its final six-service PASS, including the assertions previously unreachable after line72. |
| `env -i PATH="$PATH" docker compose --env-file /dev/null -p mcpbench -f compose.yaml --profile '*' config --quiet` | PASS exit0, chunke0746e. |

Inspected correction: only absent or empty-object IPAM is tolerated. Regression tests exercise all four combinations of absent/empty IPAM across the two networks. Both roles reject nonempty IPAM, null/list IPAM, false/integer external flags, wrong identity, missing name/external, unknown/internal/driver fields; missing or additional networks also fail. Existing service limits, credential/mount scopes, loopback publication, log settings, image pinning and pull-policy checks remain present. No daemon mutations, SQL, model, image builds or credential reads occurred during recheck. The original medium checker defect is resolved at this new candidate; no remaining observed source defect blocks the focused source gate. Root still owns runtime admission and T019 completion.

The following sections record the **original `53c62bd` verification**, including the original failure.

## Commands and actual results

Commands ran in the frozen worktree. `PY` below means `/home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python`; all Python runs used `PYTHONDONTWRITEBYTECODE=1`. Versions: Go1.26.8 linux/amd64, Python3.14.4, Docker Composev5.4.0, pinned MCP Go SDKv1.8.0.

| Command | Actual result / execution handle |
| --- | --- |
| `MCPBENCH_TEST_PYTHON=$PY GOMAXPROCS=1 GOTOOLCHAIN=local GOPROXY=off go test -mod=readonly -p=1 -count=1 ./...` | PASS exit0, session43301. All tested packages passed; no-test command packages reported explicitly. Integration live tests skipped. |
| `$PY -m unittest launcher.test_transport launcher.test_run -q` | PASS exit0, 15 tests, 2.327s, session15251. |
| `$PY -m unittest contracts.tests.test_contracts eval.runner.test_lifecycle eval.runner.test_artifacts -q` | PASS exit0, 83 tests, 8.921s, session86243. Expected fixed-phase rejection diagnostic appeared during a negative test. |
| `$PY containers/check_config.py` | **FAIL exit1**, chunk2bde92, assertion at line72 comparing rendered networks. |
| `env -i PATH="$PATH" docker compose --env-file /dev/null -p mcpbench -f compose.yaml --profile '*' config --quiet` | PASS exit0, chunk6ec21e. Configuration rendering only; no daemon mutation. |
| Same sanitized Compose render with `config --format json`, piping only `networks` to Python | Exit0, chunka80dcf. Both expected external named networks additionally contain `ipam: {}`. |
| `MCPBENCH_TEST_PYTHON=$PY GOMAXPROCS=1 GOTOOLCHAIN=local GOPROXY=off go test -mod=readonly -p=1 -count=1 -v ./internal/gateway ./tests/integration` | PASS exit0, session30393. Four gateway tests pass; two integration tests explicitly SKIP/UNRUN because root admission is absent. |
| Inline pinned-Python assertions importing `DockerTransport` and synthetic `FRESH/NETWORK/MCP/IMAGES` fixtures | PASS exit0, chunk1a3095: 9 strict-image negatives and 9 additional identity/address/network negatives (below). No subprocess/container/credential access. |

## Criterion evidence

| Criterion | Result and practical limit |
| --- | --- |
| Real pinned SDK through gateway | PASS: actual loopback client → gateway → real billing MCP HTTP handler negotiates/connects, discovers authorized tool, returns structured result, then rejects call after revocation; service call counter remains1. Synthetic billing service, no PostgreSQL. |
| Fixed routing and request bounds | PASS: destination/Host/Origin/auth forwarding; denied path/query/method/Host/Origin; oversized body/header rejected before upstream. Source fixes upstream and disables proxies. |
| Response/cancellation/concurrency/no redirects or retry | PASS: oversized response502; cancelled request propagates cancelled context; fifth simultaneous request503 while four forwards are held; redirect response forwarded after exactly one RoundTrip. Source disables keepalive, clears GetBody, sets Close, makes one RoundTrip and never follows redirects. Active midflight cancellation, real six-second deadline expiry and network lost-response replay were not independently fault-injected in this offline run. |
| CID/image/network/IP negatives | PASS: candidate tests reject mismatched CID/image, stopped state, extra network, network-ID mismatch, missing/invalid/outside IPv4, ownership/internal/name errors. Additional inline checks reject paused status, wrong driver, empty network ID, unspecified/loopback/multicast/IPv6 and subnet network/broadcast addresses. |
| Strict image config | PASS: exact four-role IDs accepted by normal tests; inline negatives reject each missing role, extra role, mutable tag, uppercase hex, short digest and empty digest. Gateway image joins trusted metadata via existing four-image map. |
| Service receipts, quarantine, scoped close | PASS offline: fresh MCP/gateway receipt IDs, per-run fixed MCP IPv4, partial-start reuse rejection, preexisting receipt preventing start, shared exact-CID close/removal and separate retained logs; close failure preserves service identity. Existing lifecycle tests prove transport/unknown-fence/missing-trace/invalid-verifier quarantine and no reset/retry, restart barrier, quota, and narrow child mounts. These are mocked transport tests, not actual daemon/reaping proof. |
| Credential mounts/hardening/resource limits | Source and mocked command inspection PASS: gateway has no mounts, MCP retains three narrow mounts, agent/verifier retain their three; nonroot/read-only/cap-drop/no-new-privileges; gateway64MiB/0.1CPU; uncompressed single1MiB logs; only gateway loopback publication. Effective runtime values remain UNRUN. Static checker confirms earlier assertions but aborts before later network/log checks. |
| Deployment static checker | FAIL: expected networks equality excludes renderer's empty `ipam` property. Sanitized rendering succeeds; benign output normalization needs correction and independent rerun against a new frozen candidate. |

## Defect

**Medium — required static gate fails reproducibly:** `containers/check_config.py:72` expects exact network dictionaries `{name, external}`; Composev5.4.0 emits `{name, external, ipam:{}}`. Observed JSON: `{"db":{"external":true,"ipam":{},"name":"mcpbench_db"},"front":{"external":true,"ipam":{},"name":"mcpbench_front"}}`. Root was notified. Do not waive the failed required check or interpret downstream assertions as having run. No production/source fix was made by the tester.

## Explicit runtime UNRUN

No builds/pulls/installs, service/network/container startup, Docker daemon mutations, SQL connections, model calls, credential reads or native configuration changes occurred. Real image IDs/builds, front-network ownership/subnet nonoverlap, effective CID/network/port/mount/cap inspection, host health/SDK denied-caller zero-write evidence, measured gateway resource usage and unchanged19-service baseline require root admission. Real full-stack25000-cent grading, wrong-write failure, same-key/conflict replay with unchanged state, concurrent duplicate, timeout-after-commit and seed restoration remain UNRUN. `TestConcurrentDuplicate` and `TestTimeoutAfterCommittedResponse` explicitly skipped. Preserve existing quarantined runs/resources; this source verification authorizes no reset, cleanup or T019 completion.
