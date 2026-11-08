# T040 revised preflight safety review

Verdict: **SAFE TO RUN** the single admitted T040 request after the independent tester also passes. No open P0/P1 findings.

Frozen controller: `artifacts/probes/t040-20261108-01/controller.py`, SHA-256
`cdccf2562534762f9ba2c5755bbaeaf905dc8b1ee13e9beab29beb1b2794a1fc`.
Context: `state/task-context/T040.md`, SHA-256
`2d99c658dbcc0779c6c86b732207f216093dcb176804c00284776c4b00bad051`.
The controller hash was independently verified. The initial P1 report is retained
at `state/reviews/T040-preflight-reviewer-v1.md`.

The initial P1 is resolved: `sample_bounded()` executes only the read-only
`--sample` branch in a child process under an aggregate 1.5-second timeout.
Preflight, live and post-request observations use this wrapper. The live loop
retains its two-second monotonic schedule; a timeout or other observation failure
enters the exception path and then terminates the owned curl process, preserving
an explicit failed outcome. Blocking Docker or Ollama metadata calls can no longer
extend an accepted live observation to the previous cumulative timeout budget.
The child branch neither invokes main nor performs inference.

The revised fixed source retains all other reviewed boundaries: installed
qwen3.5:9b/digest identity, >=20 GiB current RAM and relevant disk, empty residency,
no active Ollama connection, admitted workload identity/health, exactly one curl
request without retry, 120-second curl deadline, one-MiB response cap, and
request-local 4096 context/512 output/temperature zero/seed zero/think=false/two
CPU threads. The sole exposed tool is probe_echo with strict arguments and local
fixed-text validation. No model-proposed code is executed.

Live monitoring enforces RAM below 8 GiB for three samples, swap activity for
three intervals, and container state/health/OOM changes as failures. Curl
cancellation does not stop or unload Ollama. Five post-request observations
retain evidence and fail the attempt if observation or container state changes.
No service mutation, configuration edit, pull, forced unload, billing/MCP write
or container startup is present. Request-local keep_alive=30s remains explicit.

No inference or service operation was performed for this review. Actual request,
response, observed sampling cadence, resource safety, tool validation and final
artifact hashes remain **UNRUN** and require post-run independent review/testing.
This verdict applies only to the identified controller and one bounded T040
probe under the accepted T001/T007 admission; it does not authorize another
inference request, application implementation or Compose startup.
