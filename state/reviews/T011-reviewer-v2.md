# T011 focused independent re-review

Candidate: `e0ccb15b10a3075578d512fc1809af5e78871fc6` in `.worktrees/T011`.
Repair comparison: `7238a029c1425d036dab4231b846c63195dc0466` → candidate above.
Verdict: **APPROVE** for this focused repair review. Prior P1 is resolved; no new P0/P1 identified in the repair.

## Resolved P1 — Standalone seed inventory omission

`db/manage.py:_seed` now calls the existing `_check_shape(conn, name)` after validated migration metadata and before `_tables`, canonical no-op return, or any seed insert. Public `seed()` already invokes `_seed` inside its owned transaction after locking/validating the registered prepared mapping. `prepare()` also reaches the same guarded helper. Consequently, additional table/column inventory can no longer bypass this compatibility gate through standalone seed, whether application tables contain the canonical seed or are empty.

The new offline regression uses the real `_check_shape` inventory comparison, mocking only metadata/catalog rows and the application-reader boundary. It supplies both an extra table and an extra column, each with canonical and empty application states. It requires the inventory error, zero `_tables` calls and exactly one parameterized catalog SELECT, establishing that neither canonical no-op success nor inserts occur first. Existing unrelated seed tests explicitly isolate the new shape dependency rather than accidentally relying on a mock catalog.

The authored PostgreSQL regression creates an extra table or adds an extra customer column in its fresh test-owned run, checks standalone seed rejection, restores the alteration in `finally`, then requires canonical seed success. It remains behind the existing T018 opt-in gate and does not claim executed SQL semantics. README wording now matches the repaired ordering and retains its compatibility-versus-forensic limitation.

## Scope, evidence and limits

Read the prior reviewer report, focused four-file repair diff, `_seed`/`_check_shape` and public callers, relevant test setup and T011 context. Candidate HEAD and clean source state were verified. This review did not reopen unrelated migration/schema/grant design already covered by the prior report. Only this review file was written; no candidate/Git changes or test execution occurred.

The orchestrator's independent offline/adversarial check PASS remains required for integration. Actual PostgreSQL syntax/catalog visibility, ALTER/restore behavior, transactions/rollback, grants, storage, concurrent locks, seed-twice and upgrade remain **UNRUN until T018**. No DB connection, SQL execution, container/image operation or inference was performed. Approval does not authorize those actions or task completion.
