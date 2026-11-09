# T018 dedicated-cluster grant repair — independent test

Candidate: `8707121b4771183148e59c7abb6496e757b02b20`, inspected clean in
`.worktrees/db-grants`. Verdict: **PASS for the narrow grant correction**.
No observed defect in the assigned scope. This does not complete all T018 gates.

## Actual independent verification

On 2026-11-08 local time, read-only Docker inspection verified the exact running,
healthy owned container
`86a17f3d5a78e47cedcdd43ea2782c5ac663cdac2e09133bba05130bf372c329`:

- Image ID `sha256:73bedc9eaa0121b92b9b26bb52e5141b3f6f37479c7ef913c0160455763ca80a`.
- Compose project `mcpbench`, service `db`, project working directory
  `/home/sfkim/projects/mcpbench`, and config `/home/sfkim/projects/mcpbench/compose.yaml`.
- No published host ports; only the `mcpbench_db` network, verified internal and
  labeled for MCPBench; mounted `mcpbench_db-data` volume also labeled for MCPBench.
- Database IP matched the existing private bootstrap reference before connections.

The existing passed admission artifact was inspected. No startup, image operation,
role/grant change, or other infrastructure mutation was performed by this tester.

Copied the root helper to `artifacts/admission/t018/run_independent_grants.py`,
changed only its output destinations to preserve root records, and added ownership
assertions plus an independent effective-privilege audit. Private credentials
remained inside the Python process. Actual connections used the verified owned
container IP, fixed port 5432 and database `mcpbench`; no default or homelab
PostgreSQL database was contacted. Each of the three roles successfully connected
and its database/user identity was checked.

Independent read-only effective privilege audit, using each role's own connection:

| Runtime role | postgres CONNECT | template0 CONNECT | template1 CONNECT | mcpbench CONNECT |
| --- | --- | --- | --- | --- |
| mcpbench_controller | false | false | false | true |
| mcpbench_service | false | false | false | true |
| mcpbench_grader | false | false | false | true |

**PASS:** all nine forbidden checks and all three allowed checks.

## Executed regression

From `/home/sfkim/projects/mcpbench`:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/home/sfkim/projects/mcpbench/.worktrees/db-grants /home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python artifacts/admission/t018/run_independent_grants.py
```

The unchanged candidate test
`db.tests.test_postgres.PostgreSQLTests.test_runtime_roles_connect_only_to_benchmark_database`
ran against real PostgreSQL with only its connection factory patched to the
verified owned IP and private credentials. **1 test PASS in 0.094s; 0 failures,
0 errors, 0 skips**. Its assertions independently check nine denied effective
CONNECT combinations plus three allowed combinations. Test setup prepared one
synthetic generated run; registered cleanup completed without error. The helper
neither changes grants nor connects to the forbidden databases.

Preserved independent artifacts:

- `artifacts/admission/t018/independent-grants.json`
- `artifacts/admission/t018/independent-grants.redacted.txt`
- `artifacts/admission/t018/run_independent_grants.py`

## Limits

The root's preserved pre-fix output records one test with nine failing subcases;
its post-fix output records one passing test. This tester read those records but
did not recreate the insecure pre-fix grants. Root had already applied the three
REVOKEs to this verified cluster before independent execution. Fresh bootstrap
application on a second cluster was **UNRUN**, as were broader T018 suites in this
narrow assignment. No inference, model, install, startup, stop, or cleanup of
other infrastructure ran. Candidate source was not edited.
