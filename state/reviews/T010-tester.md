# T010 independent tester — PASS offline scope
Fixed candidate7ac9006d6f7e5e15f48c6a98e0b9c2b8b8bb1aad;prior097ef179 preserved.
Root is not author. Actual cached command from candidate cwd:
PYTHONDONTWRITEBYTECODE=1 .worktrees/T008/.venv/bin/python -m unittest
 eval.grading.test_oracle eval.reset.test_contract contracts.tests.test_contracts
 eval.fixtures.test_fixtures -q
Result70testsPASS,5.795sec;no skips. Candidateclean;contracts/fixturesunchanged.

Focused regressions cover safe denial followed by successfulauthorizedread,
actual unauthorizedsuccess rejected,incomplete/interrupteddenial notmadepassing,
verifier activity rejected. Events retained rather than omitted. Separate state,
answer,read/replay evidence APIs preserve literalexpectations and trusted scopes.
Backend tests exercise actual psycopg OperationalError/IntegrityError instances
(no connections),27 call-position cases including lost acknowledgment after
mutation;allproduce sanitized failed Evidence,no retry. BaseException interrupt
propagation remains explicit. Reviewed six-file repairdiff forscope and callers.

R recheck separately required before DONE. Actual PostgreSQL snapshots/reset,
DBroles/fences/commitcertainty/concurrency remain UNRUN untilT018+. No DB/network,
container/inference/dependency operation. Fakebackend tests do not prove SQL.
Final EvaluationResult/lifecycle composition remainsT016;this is oracle code only.
