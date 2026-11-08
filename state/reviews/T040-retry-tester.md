# T040 approved retry independent tester

Verdict: **PASS** for the harmless native tool-capability probe. This does not establish MCP transport, server/agent implementation or invoice/billing correctness. No inference, API access, service changes, candidate edits or Git mutation by tester; only this report written.

Frozen manifest SHA-256 `8fca943ea13c9ab00278f9f5da681a7076d376022598d5c2d4957007e4d8f0f8`. User authorization is explicit in supplied task/context. Read tester/AGENTS/T040 policies and recovery/retry context; reused prior approved preflight. Independent actual checks below do not rely on stored admission or status PASS flags.

| Criterion | Actual result | Evidence |
| --- | --- | --- |
| Frozen manifest and file integrity | PASS | Manifest 8fca943ea13c9ab00278f9f5da681a7076d376022598d5c2d4957007e4d8f0f8; all 11 listed files match |
| Reviewed controller unchanged | PASS | Same reviewed telemetry-only controller |
| Fresh 60sec resource admission | PASS | 31 samples/60.034423230s; min RAM 24.378571 GiB; swap pages in/out [3, 0], longest streak 1 |
| Immediate pre-call RAM/disk/residency | PASS | Start metadata 8.345851s after admission finish; before RAM 24.522720 GiB; disk [246096441344, 246096441344, 246096441344]; no models during admission/before |
| Service identity/state/health/OOM unchanged | PASS | All curated maps identical across 31 admission/before/11 during/5 after; pre-existing Immich ML unhealthy only |
| Admission connectivity/names/subnet | PASS | Port18081 free; Ollama loopback; no active shared connections; names unused and candidate subnet nonoverlapping |
| Exact model identity/tools metadata | PASS | Native Ollama0.40.13, qwen3.5:9b Q4_K_M exact digest |
| Single generation and request budgets | PASS | One reviewed Popen path/no retry; exact harmless request;120sec/1MiB/4096ctx/512output; artifact evidence for this invocation, not server-wide request audit |
| Strict real response and independently computed echo | PASS | Strict duplicate-free JSON parsed independently; exactly one probe_echo(text=mcpbench-probe-v1); local echo recomputed; no billing tool or model second turn |
| Deadline, completion, token and response caps | PASS | Controller 20.174285922s; native total 19.992424515s; load 5.870140081s; prompt=290, output=32, total reported tokens=322; response 453 bytes |
| Live cadence/RAM/swap stop thresholds | PASS | 11 during samples; cadence 1.994687–2.002889s; minimum RAM 23.834133GiB; peak service cgroup 6.867653GiB; live swap in/out [18, 0], streak 1; post [0, 0], streak 0 |
| CPU/load telemetry and independent recomputation | PASS | Aggregate live CPU busy 25.75939375% across first/last during sample; first eight counters only (guest excluded), iowait 31/15835; all observations carry CPU/load fields. Host aggregate, not exclusive model CPU. |
| Post-observation and exact resident model | PASS | Five after samples retained; final names ['qwen3.5:9b']; no inference of unload or repaired GPU from API size_vram |
| Failed first attempt preserved | PASS | All old manifest files still match; failed resource-abort result retained separately |

Command evidence/method: ran one `python3` standard-library validation over frozen files. SHA-256 recomputed from bytes for all manifest entries and immutable failed01. All JSON and every resources.jsonl line independently parsed with duplicate-key and nonstandard-number rejection. Recomputed admission duration/min RAM, every swap interval/streak, all container-map comparisons, network overlap with ipaddress, listener fields and raw disk space. Recomputed live timing/RAM/service-memory extrema and aggregate CPU deltas; asserted exact response tool/argument type/value, compared independently computed echo, token counts and bounds. Inspected frozen AST for single generation subprocess path and unchanged limits; did not import/run main or invoke generation.

Scope/limits: controller plus retained artifacts demonstrate one request for this approved attempt; they are not a complete server request audit. API token/duration fields are reported measurements, not independently instrumented internals. Sampled cgroup memory does not establish exact model-only peak. Successful native echo says nothing about MCP invoice success or benchmark rankings. GPU execution split remains unverified. Separate recovery observations and any generated cache directory are outside the frozen manifest and do not replace trial evidence. No new P0/P1 or unresolved criterion blocker found.
