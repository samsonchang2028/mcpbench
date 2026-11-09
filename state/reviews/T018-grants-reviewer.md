# T018 dedicated-cluster grant repair review

Candidate: `8707121b4771183148e59c7abb6496e757b02b20` versus `1a09ec8`.
Verdict: **APPROVE** for this narrow repair. **No open P0/P1 findings.**

## Scope and reasoning

Independent read-only inspection covered the 15 added lines in
`db/bootstrap.sql` and `db/tests/test_postgres.py`, the existing bootstrap
transaction/guards, `db/README.md` ownership requirements, the frozen role table
in `contracts/PROTOCOL.md`, and the T018 context. The checked worktree was clean
at the candidate revision.

The supplied `artifacts/admission/t018/role-audit-before.json` records all three
runtime roles with CONNECT on `postgres` and `template1`, despite their restricted
role attributes. That contradicts the frozen restriction to the dedicated
MCPBench database. The artifact does not record `template0`; its pre-fix failure
is reported by the orchestrator's regression run, not independently observed here.

The patch removes PUBLIC database privileges on the three default databases
inside the existing bootstrap transaction, before granting the runtime roles
CONNECT on `mcpbench`. Newly created runtime roles have no explicit grants or
membership that would bypass this removal. The repair preserves controller
ownership, service/grader grants, and synthetic credential handling.

The regression checks effective CONNECT privileges for all nine runtime-role /
default-database combinations and confirms that each role retains CONNECT on
`mcpbench`. Effective-privilege checks cover inherited PUBLIC access directly;
they do not mistake template0's separate connection restriction for lack of a
CONNECT grant.

## Evidence and limits

`git diff --check 1a09ec8 8707121 -- db/bootstrap.sql db/tests/test_postgres.py`
passed. This reviewer executed no SQL, live tests, containers, or other runtime
operations and made no candidate-source changes. The orchestrator must retain
the actual pre-fix failing and post-fix passing test/audit evidence.

Revoking PUBLIC privileges affects the whole target cluster's default databases.
It is appropriate only under the existing dedicated-cluster ownership boundary:
the SQL database-name/control-schema guards alone do not prove cluster ownership,
as `db/README.md` explicitly states. Applying the repair to the already bootstrapped
owned test container therefore remains an operator action under verified container,
network and volume identity. This approval does not authorize access to any
existing homelab database, startup, deployment, or completion of all T018 gates.
