# T040 prospective telemetry delta review

Verdict: **IMPLEMENTATION-READY** for the reviewed telemetry delta. No open P0/P1
findings. This is not approval to execute a second inference request.

Candidate: `artifacts/probes/t040-20261108-02/controller.py`, independently
verified SHA-256
`c9809246f788daa3f118c17de44f1a59e28ba2861af3a2f30de41e7ed29ba3b9`.
Compared directly with the immutable approved first-attempt controller
`cdccf2562534762f9ba2c5755bbaeaf905dc8b1ee13e9beab29beb1b2794a1fc`.
Read `state/task-context/T040-recovery.md` and retained the original T040
context, preflight and result-review constraints.

The only change adds raw aggregate CPU counters from the first `/proc/stat`
line and host load averages from `os.getloadavg()` to each observation.
Both values are JSON-serializable; CPU counters remain raw evidence rather
than an unsupported utilization claim. The additions are local read-only
observations inside the existing sample child and its aggregate 1.5-second
deadline. Any observation failure still fails closed and cancels owned curl.

Direct diff inspection confirms unchanged preflight, exact model/digest checks,
single generation invocation without retries, 120-second curl deadline,
4096/512 request budgets, two-second live schedule, RAM/swap/container abort
thresholds, request-local keep_alive, strict echo validation and post-request
observations. No new service, configuration, model-unload, network-write or
billing behavior is introduced. Python AST parsing passed without executing
the controller or creating runtime artifacts. No inference was performed.

The failed first attempt and its blocker remain intact. A reviewer verdict,
offline tester pass or subsequent recovery snapshot cannot authorize execution.
User approval for one retry, complete fresh 60-second admission and immediate
health/model/residency refresh remain prerequisites. No threshold change or
waiver is approved. Live behavior of the prospective controller is **UNRUN**;
independent offline helper testing belongs to the tester's separate report.
