# T040 revised preflight independent tester

Verdict: **PASS** for focused P1 correction. Frozen controller SHA-256 `cdccf2562534762f9ba2c5755bbaeaf905dc8b1ee13e9beab29beb1b2794a1fc`. Prior report retained separately as T040-preflight-tester-v1.md. No main invocation or inference; candidate unchanged. Only this report written.

Command: `python3` in-memory AST/helper regression using standard-library `unittest.mock`. Verified source hash before execution. Module loaded with `__name__=offline_preflight`, so entry point was not called. One real synthetic child ran only `python3 -c 'import time; time.sleep(4)'` under the helper's unchanged 1.5-second subprocess timeout to verify actual timeout/reaping. All controller/network/Docker execution paths remained mocked or uninvoked.

| Check | Result | Evidence |
| --- | --- | --- |
| Frozen hash and syntax | PASS | cdccf2562534762f9ba2c5755bbaeaf905dc8b1ee13e9beab29beb1b2794a1fc |
| Bounded child invocation and JSON decoding | PASS | Helper successful response decoded |
| Aggregate timeout and safe sample-only argv | PASS | ((['/usr/bin/python3', '/home/sfkim/projects/mcpbench/artifacts/probes/t040-20261108-01/controller.py', '--sample'],), {'capture_output': True, 'text': True, 'timeout': 1.5, 'check': True}) |
| Actual stalled child bounded | PASS | Harmless synthetic sleeping Python child timed out and was reaped in 1.503438s; no controller child or network request invoked |
| Helper propagates CalledProcessError | PASS | No silent fallback or retry |
| Helper propagates JSONDecodeError | PASS | No silent fallback or retry |
| All observation sites use bounded helper | PASS | Before, monitor and after use sample_bounded; direct sample only in dedicated --sample branch |
| Monitor fail-closed cancellation TimeoutExpired | PASS | Extracted frozen monitor AST with only in-memory sinks, mocked process/clock/sample; curl never launched; exception aborts, terminates request once and bounded wait |
| Monitor fail-closed cancellation RuntimeError | PASS | Extracted frozen monitor AST with only in-memory sinks, mocked process/clock/sample; curl never launched; exception aborts, terminates request once and bounded wait |

P1 resolved: a single aggregate 1.5-second subprocess deadline now covers all per-sample Docker/API/proc observations. Timeout, command failure and malformed JSON propagate; the live monitor catches failures, records an abort reason and terminates only its curl request with bounded wait/kill fallback. Normal monitor scheduling remains every two seconds. Before/after observations use the same bounded helper. No automatic retry, unload or service mutation was introduced. Dedicated `--sample` dispatch prints read-only sample data and does not enter generation.

The prior 18 offline request/schema/validation checks covered unchanged sections; focused source inspection confirms request/deadlines/thresholds/validation remain unchanged. No additional P0/P1 found. Actual live response, monitoring cadence under load, cancellation behavior on native inference, observed memory budget and artifact integrity remain UNRUN pending the single authorized T040 request. This preflight PASS is not a live capability PASS.
