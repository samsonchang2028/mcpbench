# T016 independent source review

Candidate: `300a76122b75ab6522a6cc832baa892fe5642bfe`, frozen `.worktrees/T016`. Reviewed the seven `eval/runner` files, with targeted reads of the existing reset/oracle contracts, T018 backend factory and fixed component protocol.

Verdict: **CHANGES REQUIRED**. Two open P1 findings; no P0 identified in this source review.

## P1 — Production CLI passes a Path to a factory that accepts only str

Location: `eval/runner/__main__.py:50`; actual peer interface `db/lifecycle.py`, `PostgresBackend.from_private_config` at frozen T018 `047c030`.

Trigger: invoke any normal CLI phase without an injected backend. The runner passes `CONTROL / 'database.json'`, a `pathlib.Path`. The production factory explicitly requires `type(path) is str` and the exact fixed pathname. It therefore rejects every production invocation before any lifecycle work. The test at `eval/runner/test_artifacts.py:164` uses an unconstrained Mock and asserts the incompatible Path argument, so it misses the integration failure.

Impact: the executable evaluator cannot perform prepare, settle-grade or finalize through its production backend, even with valid private files and an admitted database.

Fix: call the factory's fixed default or pass `str(CONTROL / 'database.json')`. Add an interface check that respects the actual factory's accepted argument type, without opening a database or weakening the fixed-path check.

## P1 — Startup/transport delay can grant IO beyond the absolute post-agent deadline

Location: `eval/runner/lifecycle.py:49`–`:61`, used by `Evaluator.operation`.

Trigger: the launcher samples a valid budget before evaluator startup, and startup/transport consumes substantial remaining time. `Budget` starts its monotonic timer only when constructed. Before UTC expiry, `observation()` computes remaining time solely from the stale sampled `elapsed_ms` plus this new local timer; it consults the fixed UTC deadline only once that deadline has already passed. For example, an input reporting 30,000 ms remaining delivered with its fixed deadline one second away still grants a 5,000 ms backend operation.

Impact: the database operation can continue up to four seconds past the absolute 30-second lifecycle deadline. The later `budget.check()` then quarantines the attempt, but that does not undo the already granted IO extension. It also leaves startup/transport time uncharged while the deadline remains in the future. The existing test covers an already expired UTC deadline, not a nearly expired deadline with a stale remaining observation.

Fix: independently cap each operation's deadline by the time left until the immutable absolute UTC deadline as well as the continued launcher/local monotonic remaining budget. Preserve launcher observations/overruns and avoid presenting wall-clock differences as cross-producer latency measurements. Add a deterministic stale-observation case with one second until expiry and a backend timeout no greater than that remaining absolute bound, plus expiry-during-operation coverage. Do not reset the anchor or grant a fresh phase budget.

## Other reviewed behavior and limits

The runner uses the fixed three CLI phases and fixed backend import/config location; it starts no children, shells, Docker or models. The fixed transport request lives outside the writable artifact root as documented. Artifact input references are hash/size-bound, paths reject symlink components and nonregular/FIFO inputs, private modes/owners are checked, and publication uses fsynced exclusive links rather than overwriting results. The launcher remains responsible for immutable mounts and delivery of the exact phase result bytes.

Prepare validates frozen task/fixture/config identity, requires acknowledged preparation/reset and a matching seed snapshot before capability activation. Settle-grade requires reaped child evidence, an acknowledged fresh fence and a coherent agent-only capture before independent oracle/answer grading. Original correctness remains distinct from verification and comparison validity; read-only and failed originals skip verifier activation. Unknown fences/unreaped children fail closed without reset. A valid verifier is checked before the second fence/final capture; reset follows preserved settled evidence and capability revocation. Invalid/incomplete traces invalidate comparison independently, as explicitly tested. Capability material stays in separate private auth/state and public output passes registered secret redaction.

The reviewed reset/ACK/quarantine paths and immutable invocation markers contain no automatic retry. Cross-process persistent quarantine and trusted host transport/clock enforcement remain launcher obligations; new evaluator construction is not recovery authorization. Real backend transaction/role/fence semantics belong to T018 and later integration.

This reviewer ran no tests, SQL, database connections, Docker/model requests or installations, and changed no source/Git state. Root's independent tester owns scripted/cached execution results. Actual private mounts/transport, PostgreSQL settlement, real child interruption and complete multi-producer telemetry remain **UNRUN in this reviewer lane**. Re-review both fixes at a new frozen revision before approval.
