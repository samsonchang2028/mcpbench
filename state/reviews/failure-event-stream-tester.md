# Independent test: failure Event stream maintenance

Candidate: `731ab5b75414e91efea9c44d851c95b0a05c25ae` in
`.worktrees/failure-event-stream`, compared with `fa76565`.
Verdict: **PASS** for the assigned narrow offline maintenance scope. No findings.

The candidate changes only `contracts/validate.py` and
`contracts/tests/test_contracts.py`: one split-to-partition correction and one
regression. Candidate HEAD and clean worktree were verified before and after
checks. This tester did not author or modify candidate source or tests.

## Executed checks

All Python commands ran from the fixed candidate worktree using the existing T008
environment read-only, with bytecode writes disabled:

```sh
PYTHONDONTWRITEBYTECODE=1 /home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python -m unittest contracts.tests.test_contracts.Contracts.test_failure_event_survives_complete_stream_validation -v
PYTHONDONTWRITEBYTECODE=1 /home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python -m unittest contracts.tests.test_contracts eval.fixtures.test_fixtures -v
git diff --exit-code fa76565..731ab5b -- contracts/v1/schema.json contracts/v1/catalog.json eval/fixtures
git diff --check fa76565..731ab5b
git status --short
git rev-parse HEAD
```

Results:

- Focused regression: **PASS**, 1 test. A registered `failure` Event validates
  individually and as a complete single-event stream; the same event with an
  unregistered `unknown` type is rejected through EventStream validation.
- Required contract/fixture suite: **PASS**, 47 tests, zero failures/errors/skips.
  Existing event lifecycle/correlation and interrupted-stream tests remain green.
- Frozen schema/catalog/fixture preservation: **PASS**, Git byte comparison
  produced no changes and exited 0 for both frozen JSON files and the entire
  fixture subtree.
- Candidate whitespace check: **PASS**, exit 0, no output.
- Candidate identity/stability: **PASS**, final HEAD equals the fixed full hash
  above and final worktree status is clean.

Inspection confirms individual Event validation still precedes partitioning in
`validate_event_stream`, so registered event-type constraints remain enforced.
No schema, catalog, fixture, manifest or contract-policy change is introduced.
The original candidate was not rerun here: its red result is author evidence in
the supplied context; the fixed regression and suite results above are independently
observed by this tester.

## Limits

No database connections or SQL execution, container operations, image/model pulls,
builds, inference, service configuration changes, dependency installation or Git
mutations occurred. Runtime behavior is **UNRUN** and is outside this offline
validator-maintenance acceptance scope. Only this tester report was written in
the main worktree; integration and status changes belong to the orchestrator.
