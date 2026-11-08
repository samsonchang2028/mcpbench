# T011 independent review

Candidate: `7238a029c1425d036dab4231b846c63195dc0466` in `.worktrees/T011`, compared with `272ce58`. Candidate HEAD and clean source state verified before and after review. Scope is nine files exclusively under `db/`.

Verdict: **CHANGES REQUIRED**. One P1 finding, no P0 findings. This review is static and authorizes no SQL execution or runtime work.

## P1 — Standalone seed accepts incompatible table/column inventory

Location: `db/manage.py:171` (`_seed`), reached by public `seed()`.

Trigger: An already-versioned prepared run has matching `schema_migrations` metadata and canonical rows in its seven expected tables, but an extra table or extra column exists in its registered schema. `_metadata` checks the declared migration/fixture identities, not the live inventory. `_tables` explicitly selects only the seven names and listed columns; it cannot include those additional objects in the fingerprint. `_seed` therefore returns the canonical seed hash without rejecting the incompatible schema. The same state is rejected by `migrate()` because `_migrate` calls `_check_shape` on its versioned path.

Impact: The separately documented seed entrypoint can claim canonical compatible initialization while ignoring unexpected schema/data. T011 explicitly requires rejection of incompatible existing state. This is an inventory omission, within the existing `_check_shape` compatibility promise; it does not ask for forensic detection of owner-altered constraints/types or future lifecycle implementation.

Smallest useful fix: Call the existing `_check_shape(conn, name)` in `_seed` after metadata validation and before `_tables` or any insert. Add a focused offline regression establishing that incompatible inventory prevents both canonical no-op success and empty-table inserts. Author an altered-table/column case for gated T018 PostgreSQL execution; keep its actual SQL semantics UNRUN here.

## Other reviewed requirements

- **Trusted routing and locking:** Public mutations own a transaction, require an idle connection, check dedicated database/controller identity, lock the registry row FOR UPDATE before schema work, validate full frozen RunMapping and derived schema binding, and admit only prepared/generation-zero initialization. Prepared mapping validation also excludes active capability digests. Identity trigger protects routing/identity fields. Later sealing/reset/fence receipts are correctly deferred.
- **SQL construction:** Fixed migration filenames/directions; schema-shape validation plus psycopg Identifier composition; run IDs and other values bound as parameters. No DSN/environment connection creation or SQL execution occurs on import. No existing database was contacted.
- **Schema and canonical seed:** Seven table/column mappings match the frozen fixture contract. Seed comes from the existing validated corpus, without a second data copy. Version/checksum/fixture/tenant/hash identities are tracked; unversioned schema adoption and changed row fingerprints fail. Money/quantities, IDs, dates, draft/USD status, zero tax, foreign keys, unique idempotency, line positions and numeric aggregate arithmetic are represented in SQL. Deferred checks cover invoice header/line/ledger atomic completeness; canonical prices/request hashing correctly remain T012 responsibilities.
- **Privilege design:** Bootstrap is documented for a verified new dedicated project DB only, with database-name checks explicitly insufficient for ownership. Controller lacks cluster superuser/create-role/create-db rights. Service gets registry SELECT plus column-specific UPDATE(lock_marker), app SELECT, and INSERT only on invoice/header ledger tables; no business UPDATE/DELETE or lifecycle column update. Grader receives SELECT without row-lock UPDATE rights and a read-only default. No passwords, trust authentication or broad PUBLIC grants introduced.
- **Rollback and migration:** Transactional version 0↔1 helpers preserve registry identity, reject active phases and noncanonical business state, retain checksum identity, use non-CASCADE drops and roll back errors. These are initialization helpers, not a claim of safe post-agent reset.
- **Tests/documentation:** Offline tests cover fixture/hash agreement, renderer injection/direction rejection, phase rejection, nested transactions, changed/canonical seed behavior. Future opt-in tests are authored for seed/reconnect, rollback/upgrade, checksum mismatch, SQL constraints/atomic failures, valid service insert/idempotency uniqueness, least privilege and conflicting row locks. The offline tests do not yet cover the P1 inventory bypass. README clearly separates offline results from future dedicated-network/bootstrap/runtime commands.

## Evidence and limits

Read reviewer instructions, T011 context, frozen protocol/RunMapping validation, relevant architecture/fixture requirements, all nine candidate files and their focused diff scope. `git diff --check 272ce58..HEAD` passed. No candidate or test file was changed. No tests were executed by this reviewer; the orchestrator is the independent tester for this candidate.

Actual PostgreSQL syntax, trigger execution, grants, concurrent locks, transactional commit/rollback behavior, seed-twice and upgrade on real storage remain **UNRUN until T018**. Static source inspection neither proves nor falsely fails those runtime properties. No container startup/build/pull, SQL connection, service change or model inference occurred. Re-review the fixed seed inventory path and its regression evidence before approval.
