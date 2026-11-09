# T018 lifecycle service-keyword focused review

Candidate: `f2c4dc9fff47567d826275c343dcb1b2b1a066ee`, compared with `047c030`, in `.worktrees/T018`. Scope: the three-file service-keyword patch, the production connection/environment guards, and the prior adapter source review in `T018-backend-reviewer.md`.

Verdict: **APPROVE for this focused source change.** No P0/P1 or other actionable findings identified. The prior adapter review remains applicable to unchanged code; this approval does not establish T018 runtime readiness or authorize workload startup.

## Findings and boundary checks

- `db/lifecycle.py:82`: removing `service=''` removes the explicit empty named-service lookup that the operator reports failed against the owned PostgreSQL instance. The patch adds no alternative service selection or configurable connection endpoint.
- `db/lifecycle.py:110`: the unchanged production factory checks every inherited `PG*` variable against exactly `PGHOST=db` and `PGDATABASE=mcpbench` before evaluating `_resolve(deadline)`. Thus both `PGSERVICE` (including an empty value) and `PGSERVICEFILE` still raise a contract error before DNS, conninfo construction, or connection attempts. Omitting `service` from conninfo does not permit either inherited override through this factory.
- The fixed `db:5432/mcpbench` destination, resolved single IPv4 address, dedicated `mcpbench_controller`/`mcpbench_grader` identities, explicit password, `/dev/null` passfile, disabled TLS/GSS, and fixed search path remain unchanged. Production construction continues to select only the two dedicated role factories from the validated private configuration.
- `db/tests/test_lifecycle.py:322`: the added conninfo regression checks absence of the `service` keyword and fixed host, address, database, and identity for both roles. The expanded environment regression independently covers `PGHOSTADDR`, nonempty/empty `PGSERVICE`, and `PGSERVICEFILE`, with a clean environment and an assertion that DNS was never called. These checks cover the scope of this fix without changing the factory interface.
- `db/LIFECYCLE.md` accurately describes the omitted keyword and continued environment rejection. No frozen contract or lifecycle-state behavior changes.

## Evidence and limits

The orchestrator reports **41 offline tests PASS** after the patch. That is supplied evidence, not a test execution by this reviewer. This lane executed no tests, SQL, connections, containers, or model operations, and made no source, runtime, or Git changes. Only this report was written.

The originally reported owned-PostgreSQL failure motivated this change; successful live retry, role/grant checks, fencing/concurrency, reset/oracle validation, and timeout/lost-ACK acceptance remain with the independent runtime gate. Those checks are **UNRUN by this reviewer**. No additional source issue in this patch blocks that gate from proceeding under its existing admission rules.
