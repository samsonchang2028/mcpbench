# T040 actual-result independent review

Decision: **APPROVE the retained failure record; T040 attempt FAIL and capability
gate BLOCKED. T040 is not complete.** No retry or resource-policy change is
approved by this review. No new P0/P1 controller defect was found; the observed
sustained-swapping condition is a P1 runtime safety blocker for further live work.

Candidate: `artifacts/probes/t040-20261108-01/hashes.json`, SHA-256
`54e3d8333fe2da0818cdfffa5fd8f2e7cad00e9a204c952a9e10110af80f49a1`.
Every listed artifact independently matched its SHA-256. Controller hash remains
the approved `cdccf2562534762f9ba2c5755bbaeaf905dc8b1ee13e9beab29beb1b2794a1fc`.
Review covered request, controller, model identity, metadata, before/live/after
observations, curl stderr and status. No inference or service operation was
performed during review.

## Observed outcome

The saved request targets installed qwen3.5:9b with the reviewed digest and
request-local 4096/512 limits, temperature zero, seed zero, think=false, two CPU
threads and keep_alive=30s. It exposes only the fixed harmless probe_echo tool.
The controller has one generation invocation and no retry. Metadata identifies
source revision `683dcd79dde855aed163b7722f3de1d51139324f` and a 120-second
deadline. Preflight recorded approximately 25.13 GiB available RAM, more than
20 GiB disk, no resident model and the admitted container inventory.

Nineteen retained live observations span the attempt, with successive intervals
between 1.95756 and 2.03116 seconds. Minimum live available RAM was 24.78710 GiB;
the RAM threshold did not trigger. The final consecutive intervals had these
independently recomputed swap-in/swap-out page deltas:

| Observation UTC | Swap in pages | Swap out pages |
| --- | ---: | ---: |
| 15:34:51.607371 | 0 | 8,155 |
| 15:34:53.621599 | 3 | 43,527 |
| 15:34:55.604154 | 66 | 12,390 |

Each interval has swap activity, satisfying the unchanged three-consecutive-
interval stop rule. `status.json` correctly records sustained swapping, FAIL,
elapsed 36.204355 seconds and curl return code -15 (SIGTERM). The reviewed
controller terminates only its owned curl process on that branch. This was a
safety interruption before the request deadline, not an HTTP/model timeout.
`response.json` is absent and curl stderr is empty. No returned tool call,
argument validation or local echo result exists; metadata cannot substitute for
that missing capability proof. Tool support and end-to-end billing remain unproven.

## Health, cancellation and uncertainty

All 19 live container inventories and all five post-request inventories compare
equal to the preflight baseline, including identities, start times, OOM flags,
state and declared health. The existing unhealthy Immich ML status remains;
there is no observed new container health/OOM regression. This does not establish
latency or functional health for services without declared checks.

The five retained post-request observations continue through
2026-11-08T15:35:06.554756+00:00. The model remains resident with the expected
digest, and swap-in advances another 3,243 pages after the final live reading;
swap-out does not advance further in that window. Cancellation therefore must
not be described as immediate model release or full host recovery. No forced
unload or service/configuration mutation appears in the reviewed controller.
Observed Ollama cgroup memory peaks at approximately 6.34 GiB; this is a cgroup
observation, not a complete inference-memory attribution. API size_vram metadata
does not resolve the previously observed NVML mismatch or prove usable GPU state.

Swap counters are host-global. The artifacts establish the stop condition, not
which process caused it. High available RAM does not negate the measured swap
activity or authorize relaxing the rule. A separate timestamped read-only
recovery observation may document later model residency, swap and service health;
it must remain distinguishable from this frozen attempt and cannot turn its FAIL
into PASS.

Subsequent independent artifact inspection confirmed the separate
`recovery-observation.json`, SHA-256
`0a10b02ff84aba43d2845bc3de638de382c22f9924ea417c085c52158729260e`,
which is outside the original manifest. At 15:35:46.972208 UTC its model list is
empty and all container records still equal baseline. Its swap counters are
577,150 in / 2,264,483 out pages. This supports later natural model expiry and
preserved declared health, not a new 60-second no-swap admission sample.
`state/audits/2026-11-08-T040-result.json` records separate read-only diagnostics:
service MemoryPeak 11,491,008,512 bytes, MemoryHigh/MemoryMax infinity and host
swappiness 60. The cgroup's service-lifetime peak is distinct from the lower
sampled peak and does not identify model-only memory or explain swap causality.
These observations do not alter the original failure or justify a policy change.

## Gate disposition

Preserve this interrupted attempt and its immutable hashes. T001/T007 remain
historical accepted admission observations, not continuing permission to run.
T040 remains blocked on sustained swapping and has no successful capability
result. T008 and other T040-dependent work must remain gated. Any future live
attempt requires resolution of the blocker, fresh admission and the appropriate
reviewed authorization; this review authorizes neither a retry nor changed
thresholds. Do not unload models, clear swap/cache, change native Ollama settings,
restart unrelated services or modify GPU configuration to manufacture a pass.
