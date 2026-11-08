# T040 approved retry independent result review

Verdict: **APPROVE**. The retry satisfies T040's harmless native tool-call
acceptance criteria with no open P0/P1 findings. Independent tester approval and
orchestrator integration remain necessary before marking T040 complete.

Candidate: `artifacts/probes/t040-20261108-02/hashes.json`, independently
verified SHA-256
`8fca943ea13c9ab00278f9f5da681a7076d376022598d5c2d4957007e4d8f0f8`.
Every listed file matches its hash. The controller remains the reviewed
`c9809246f788daa3f118c17de44f1a59e28ba2861af3a2f30de41e7ed29ba3b9`.
Read the retry-results context and reviewer instructions; evaluated against the
previously reviewed T040 acceptance, admission and stop policies. No inference,
Git change or candidate modification was performed during review.

## Acceptance evidence

| Criterion | Observed result |
| --- | --- |
| Authorized bounded retry | PASS: supplied context records explicit user approval for one gated retry; frozen controller has exactly one curl generation invocation and no automatic retry. |
| Exact native model | PASS: version 0.40.13; installed qwen3.5:9b, Q4_K_M, digest `56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90`; admission tags and immediate preflight tags agree. Loaded metadata and response identify the expected model. |
| Fresh admission | PASS: independently recomputed 31 retained observations over 60.034423 seconds; minimum MemAvailable 24.37857 GiB; three swap-in pages in two isolated intervals, zero swap-out, longest swap-active streak one. All admission container records match the accepted baseline and all residency lists are empty. |
| Disk, ownership and connectivity | PASS: fresh relevant-filesystem readings exceed 20 GiB, immediate preflight retains 246,096,441,344 available bytes per path. Loopback Ollama listener and empty before/after admission connections are retained; TCP 18081 is unused. No proposed MCPBench resources appear; independently checked subnet 172.30.77.0/24 has no overlap with retained routes/Docker subnets. Earlier authenticated model-target evidence remains the storage provenance. |
| Limits | PASS: request-local 4096 context, 512 output, temperature zero, seed zero, think=false, two CPU threads and 30-second keep_alive; controller retains 120-second curl deadline, one-MiB response cap and aggregate 1.5-second observation timeout. No global setting changes or explicit unload are present. |
| Actual tool output | PASS: independently parsed response with duplicate-key rejection. It has one probe_echo call, arguments exactly the object `{"text":"mcpbench-probe-v1"}`, correct model, done=true and done_reason=stop. Local echo independently reproduces the saved `local_tool_result`. No arbitrary returned code is executed. |
| Honest runtime outcome | PASS: curl exit zero, empty stderr, no abort reason; controller elapsed 20.174286 seconds. Response reports 19.992425 seconds total, 290 prompt tokens and 32 output tokens. Model-reported duration and controller elapsed remain distinct measurements. |
| Live safety and telemetry | PASS: 11 live readings with successive intervals 1.99474–2.00289 seconds; minimum available RAM across preflight/live 23.83413 GiB. Eighteen swap-in pages occurred in two isolated intervals; zero swap-out, longest activity streak one. No three-sample stop condition occurred. Raw CPU counters and load are retained. |
| Existing services and post observations | PASS: every live and all five post-request container inventories match the original admitted 19-container state, identities, start times, OOM flags and declared health. Post-request window spans about 11 seconds from the final live reading, with zero additional swap activity. Existing unhealthy Immich ML remains unchanged. |
| Original failure preserved | PASS: independently rechecked every first-attempt manifest entry; all still match and attempt01 remains FAIL for sustained swapping. The successful retry does not replace that evidence. |

## Scope and residual risks

This is one successful harmless native tool-call probe after one retained safety
abort, not a success-rate estimate or proof of reliable billing behavior. The
response does not exercise MCP, invoice creation, database invariants, idempotency,
permissions or the independent invoice oracle; those checks remain **UNRUN**.
No app implementation, billing/MCP write, service restart, model pull or forced
unload is introduced by the reviewed controller.

Observed CPU busy from aggregate counters was approximately 8.93% during
admission and 25.81% across immediate preflight/live observations; host counters
include other workloads and are not model-only attribution. The maximum sampled
Ollama cgroup usage was about 6.87 GiB, which is not a complete inference-memory
requirement. API size_vram is metadata and does not resolve the earlier NVML
mismatch or independently prove GPU readiness.

The model remains resident at the final frozen post-request observation under
its request-local keep_alive. A later separately timestamped expiry observation
may document recovery, but was not needed to validate this successful call and
must not alter the frozen attempt. No claim of immediate unload is made.
Declared container health does not measure latency or functional health of
services without checks; shared capacity remains time-sensitive.

No required T040 evidence remains missing in this candidate. Approval permits
the orchestrator to integrate this result after the separate tester passes; it
does not authorize another generation request, waive future resource admission,
complete T023, or authorize Compose startup outside its own gates.
