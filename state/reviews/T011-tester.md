# T011 independent tester — PASS offline scope
Candidate e0ccb15b10a3075578d512fc1809af5e78871fc6;initial7238a02 retained.
Root V is not author. Actual cached command from candidate cwd:
PYTHONDONTWRITEBYTECODE=1 .worktrees/T008/.venv/bin/python -m unittest
 db.tests.test_offline db.tests.test_postgres -q
Result20 tests,11PASS,9SKIPPED(T018 PostgreSQL gate);0.076sec.
Fixture corpus CLI PASS,4tasks,exact8303fb14daf4ae93b75a9df9b2faa56ff9f28ab2d0c489689e9159ad848f9c78.
Git diffcheck PASS;contracts/fixtures byte-unchanged versus272ce58;clean candidate.

Inspected focused7238a02..e0ccb15 patch:real inventory check before application
reads/no-op hash success/inserts. Regression exercises realcatalog comparison
for extra table/column with canonical and empty data,preventing reads/inserts.
Other actual offline cases cover schema injection/direction,prepared phase,
invalid mapping before DB,nested transaction rejection,changed seed detection,
canonical repeat,no overwrites,wire dates and migrationchecksum. Existingfrozen
seed data remains authoritative;no production-code-derived expected arithmetic.

No openP0/P1 in corrected offline implementation. R recheck separately APPROVE
in T011-reviewer-v2.md. SQLsyntax/effectivegrants/FKconstraints/actualseedtwice/
upgrade/rollback/row-lock concurrency remain UNRUN:authored PG cases must really
execute atT018. No connection or SQL/container/inference operation occurred.
