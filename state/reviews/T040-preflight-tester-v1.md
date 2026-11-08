# T040 preflight independent tester

Verdict: **FAIL** pending P1 monitor-cadence fix. Frozen controller SHA-256 `b979595c42af1a8280d728ad8332acab1fdf0b0197494832d99a0a7c87594d37`. P1 confirmed: serial Docker/API observations in `sample()` can exceed the required two-second monitor cadence and defer resource-threshold evaluation. No inference or `main()` invocation; candidate unchanged. Only this report written.

Read T040 context, tester instructions, admission/stop rules and early-probe security/budget contract. Applied token-efficient-coding. Actual checks: `sha256sum artifacts/probes/t040-20261108-01/controller.py`; `python3` in-memory AST compile and module execution with `__name__=offline_preflight`, then isolated request assignment and validation AST execution using stubbed file/process/save objects. No sockets, subprocesses, sleeps or writes are invoked by these offline helper checks.

| Check | Result | Evidence |
| --- | --- | --- |
| Syntax/AST compile | PASS | Compiled in memory; no pycache or candidate write |
| Duplicate keys rejected {"text":"a","text":"b"} | PASS |  |
| Duplicate keys rejected {"a":{"x":1,"x":2}} | PASS |  |
| Exact bounded request | PASS | 4096 context /512 output/2 threads/temperature0/seed0; one harmless tool; request-local settings |
| Strict tool schema | PASS |  |
| Validation: valid tool call | PASS | {'outcome': 'PASS', 'validated_call': {'name': 'probe_echo', 'arguments': {'text': 'mcpbench-probe-v1'}}, 'local_tool_result': {'text': 'mcpbench-probe-v1'}} |
| Validation: wrong model | PASS | {'outcome': 'FAIL', 'validation_error': 'incomplete/wrong model response'} |
| Validation: incomplete | PASS | {'outcome': 'FAIL', 'validation_error': 'incomplete/wrong model response'} |
| Validation: output exhausted | PASS | {'outcome': 'FAIL', 'validation_error': 'output cap reached'} |
| Validation: no call | PASS | {'outcome': 'FAIL', 'validation_error': 'expected exactly one tool call'} |
| Validation: two calls | PASS | {'outcome': 'FAIL', 'validation_error': 'expected exactly one tool call'} |
| Validation: unknown tool | PASS | {'outcome': 'FAIL', 'validation_error': 'unknown tool'} |
| Validation: extra argument | PASS | {'outcome': 'FAIL', 'validation_error': 'invalid argument shape'} |
| Validation: wrong text | PASS | {'outcome': 'FAIL', 'validation_error': 'invalid echo argument'} |
| Validation: non-string text | PASS | {'outcome': 'FAIL', 'validation_error': 'invalid echo argument'} |
| Validation: string argument object | PASS | {'outcome': 'FAIL', 'validation_error': 'invalid argument shape'} |
| Abort/HTTP failure rejected ('monitor failure', 0) | PASS |  |
| Abort/HTTP failure rejected (None, 28) | PASS |  |

Manual safety/control checks: FAIL on monitor cadence; other inspected controls pass. Exactly one curl `/api/chat` process, no retries, 120-second curl deadline plus monotonic monitor bound, 1 MiB response cap, loopback endpoint, 30s local keep-alive, no unload/config/pull/build/service mutation. Pre-call exact tag/digest, >=20GiB RAM/disk, empty residency/connection and exact prior container baseline asserted. Monitor scheduled at 2-second intervals, with RAM<8GiB and swap activity requiring three consecutive samples; any container baseline change or monitor exception fails and terminates only owned curl, then bounded wait/kill. P1: monitor sampling performs serial 3-second Docker/API observations before evaluating RAM/swap. A slow or failing observation can defer resource evaluation beyond two seconds. Curl independently bounds request duration, but does not enforce resource observation cadence. Root is preparing a bounded total-sample fix; this frozen hash is not admitted for inference. Cancellation is not claimed to stop server inference. Five post-call samples preserve continued observations without forcing unload; observation errors/container changes downgrade outcome. Strict JSON duplicate detection, exact function/argument/text and response completion validated; local echo is computed without running arbitrary tools. The monitor captures service cgroup memory for later >12GiB budget assessment; metadata file size is not substituted for runtime memory.

Actual live call, deadline behavior under live load, monitor samples, response correctness and artifact hashes remain UNRUN until the single authorized T040 request; this report establishes offline preflight only. Whole-request completion can precede/follow sample observation by bounded sampling latency; actual request/controller elapsed evidence must be assessed after execution. No second model request is authorized by this test.

The 18 offline syntax/request/validation cases passed. No additional P0/P1 identified in those checks. Await revised controller hash for focused retest.
