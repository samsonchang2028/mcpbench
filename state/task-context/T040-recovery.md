# T040 prospective second probe — not authorized to run
Existing failed attempt remains immutable at artifacts/probes/t040-20261108-01/.
Root owns only prospective artifacts/probes/t040-20261108-02/controller.py.
Delta adds raw /proc/stat CPU ticks and load fields missing from first attempt.
No generation, new admission, retry or threshold change is authorized by this pack.
Frozen candidate SHA256: c9809246f788daa3f118c17de44f1a59e28ba2861af3a2f30de41e7ed29ba3b9
R owns state/reviews/T040-recovery-reviewer.md; V owns T040-recovery-tester.md.
Read agents role instructions, state/task-context/T040.md and prior preflight/result
reports. Verify delta only, unchanged1.5sec sample bound,120sec deadline,4096/512
budgets,2sec monitoring and stop thresholds. Test helper offline without main or
live inference. R/V assess implementation readiness only, not runtime approval.
Pending user decision on one gated retry; full fresh60sec admission and immediate
health/model/residency refresh remain mandatory before any second request.

User now explicitly approved one gated retry. Historical unauthorized labels
above describe candidate review time. Fresh admission still required; no automatic
further request and no threshold/config changes. Root holds resource lease.
