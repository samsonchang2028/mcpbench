# T040 preflight safety review

Verdict: **CHANGES REQUIRED** before the single inference request.
No P0 finding; one P1 finding.

Frozen controller: `artifacts/probes/t040-20261108-01/controller.py`, SHA-256
`b979595c42af1a8280d728ad8332acab1fdf0b0197494832d99a0a7c87594d37`.
Context: `state/task-context/T040.md`, SHA-256
`2d99c658dbcc0779c6c86b732207f216093dcb176804c00284776c4b00bad051`.
Read-only review against the T040 context, accepted admission evidence,
IMPLEMENTATION_PLAN admission/stop rules and SECURITY_RESOURCE_CONTRACT's
resource and early-probe sections. No inference or service mutation performed.

## P1: external inventory calls can stall the safety sampling loop

Area: controller.py:29–47 and 106–127.

`sample()` reads memory/swap, then synchronously calls `inventory()` (two Docker
commands with separate three-second timeouts) and `api('ps')` (a three-second
socket timeout). The low-memory/swap checks run only after all three operations
return. If Docker and Ollama are slow but each returns before its individual
timeout, each iteration can take nearly nine seconds. The next scheduled sample
then starts late without detecting the cadence violation. The urllib timeout is
also an individual blocking-I/O timeout, not an aggregate sample deadline.

Trigger: degraded/slow Docker or Ollama metadata responses during model loading
or host pressure. Impact: the required two-second resource sampling and timely
three-sample safety abort are not enforced precisely when the host is stressed.
Scheduling `next_sample += 2` cannot recover the missing observations, and a
valid model response could still receive PASS despite prolonged monitor gaps.

Smallest useful fix: enforce one aggregate deadline shorter than the sampling
period for each complete observation, cancel the owned curl process and retain
an explicit monitor-failure outcome when it expires. Alternatively, isolate fast
memory/swap sampling and abort enforcement from potentially blocking inventory
calls, with a bounded health-observation deadline. Do not wait for stalled
workers before cancelling the request. Re-review the revised frozen controller
before invoking inference.

## Other required safety checks

The fixed source otherwise checks installed tag/digest, >=20 GiB RAM and disk,
empty model residency, no active Ollama connections, and exact admitted workload
state before launching. One curl invocation has a 120-second request deadline,
one-MiB response cap and no automatic retry. Request options set 4096 context,
512 output, temperature zero, seed zero, think=false and two CPU threads.
The only exposed tool is the harmless fixed echo; strict duplicate-key parsing,
single-call validation and local echo computation are present.

Threshold values themselves match policy: RAM below 8 GiB for three samples,
swap activity for three intervals, or container state/health/OOM change causes
failure. Cancellation terminates only the owned curl process. Post-request
observations are retained; no explicit unload, pull, configuration edit, service
restart, billing/MCP write or container mutation appears. keep_alive=30s is
request-local. These findings do not waive the monitoring issue above or claim
runtime validation; all live response and resource results remain UNRUN.
