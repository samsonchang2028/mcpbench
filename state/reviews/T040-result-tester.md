# T040 independent result tester

Overall capability verdict: **FAIL**. Safety-abort handling: **PASS**. This is a retained failed/interrupted attempt, not proof that model tool calling is unsupported. No inference, retry, configuration, permission or service operation performed by tester. Only this report written.

Candidate: `artifacts/probes/t040-20261108-01/hashes.json`, SHA-256 `54e3d8333fe2da0818cdfffa5fd8f2e7cad00e9a204c952a9e10110af80f49a1`; controller matches revised preflight. Tested 2026-11-08T15:36:25.821261+00:00.

| Criterion | Actual result | Evidence |
| --- | --- | --- |
| Frozen artifact integrity | PASS | 9 manifest entries independently rehashed; controller cdccf2562534762f9ba2c5755bbaeaf905dc8b1ee13e9beab29beb1b2794a1fc |
| Approved controller identity | PASS | Same controller as revised preflight; extra nonmanifest files ['recovery-observation.json'] are outside this frozen result |
| One bounded request path | PASS | One reviewed curl generation path; no retries. Artifacts record this attempt, not an independent server-wide request audit |
| Exact request budgets | PASS | 4096 context, 512 output, 2 threads, temperature0, seed0, 30s local keep-alive; one harmless tool |
| Abort at first three-sample swap streak | PASS | First qualifying streak ends at sample 19/19; final intervals [(17, '2026-11-08T15:34:51.607371+00:00', 0, 8155, 1), (18, '2026-11-08T15:34:53.621599+00:00', 3, 43527, 2), (19, '2026-11-08T15:34:55.604154+00:00', 66, 12390, 3)] |
| Monitor cadence and prompt cancellation | PASS | 19 during samples; span 36.001617s; intervals 1.957560–2.031160s; status finish 0.147667s after final sample; curl SIGTERM -15; elapsed 36.204355136s |
| Precall memory/disk admission | PASS | Before RAM 25.130932 GiB; disk [245553610752, 245553610752, 245553610752]; no resident model |
| RAM monitored without low-memory abort | PASS | Min before/during/after MemAvailable 26614947840 bytes=24.787102 GiB; peak Ollama service cgroup 6809079808 bytes=6.341450 GiB; this is sampled service memory, not proven model-only peak |
| Existing service health/identity/OOM preserved | PASS | All 19 full curated container maps identical across before/19 during/5 after; pre-existing Immich ML unhealthy; no new OOM/health/state/start changes |
| No result fabricated | PASS | No response file, validated tool call, or locally computed result. Capability has no positive evidence |
| Bounded post-cancel observation | PASS | Five after samples 2026-11-08T15:34:57.808212+00:00 through 2026-11-08T15:35:06.554756+00:00; final resident models ['qwen3.5:9b']; cancellation did not establish immediate unloading |
| CPU utilization during probe | BLOCKED | before/resources/after record no CPU ticks, per-process CPU or load fields. CPU utilization cannot be recomputed; num_thread=2 is a request setting, not utilization evidence. Earlier admission CPU observation does not prove trial utilization. |
| Valid real model tool call and local echo | FAIL | Attempt safety-aborted; response unavailable. T040 capability acceptance remains unmet and downstream dependent tasks remain gated. |

Method/command evidence: executed `python3` standard-library checks only. Parsed each manifest entry and recomputed SHA-256 directly from file bytes; parsed request/metadata/status and every raw JSONL/sample; compared all container dictionaries; calculated per-interval swap deltas against before then each preceding during sample, counting consecutive active intervals and locating the first threshold crossing; recomputed all cadence/elapsed and RAM extrema from raw monotonic/resource fields. Parsed frozen controller AST to count generation subprocess sites and inspected unchanged curl deadline/response bounds. No stored success flag was accepted without underlying checks.

Additional observations: post-cancel swap activity persists in the recorded after window; do not infer stable idle recovery or immediate memory release from curl termination. The model API reports nonzero `size_vram` while resident; this is API metadata and does not establish repaired GPU runtime or measured CPU/GPU execution split. No GPU assumption is required for the correct safety abort. Any separate recovery observation is outside the frozen result manifest and was not substituted for this attempt's evidence.

Defects/limitations: no new safety-controller P0/P1 observed in this actual attempt. Runtime CPU telemetry is missing and remains explicitly unverified. Sustained swapping is an observed resource stop condition; its causal attribution to a particular shared-host process is unproven. Preserve this failure, keep T040 capability unmet, and do not retry by weakening admission/abort thresholds.
