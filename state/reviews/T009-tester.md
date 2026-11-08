# T009 independent tester — PASS

Candidate: `f6b196e9c7f070d06256ae887198afa386f52330`, base `7116a10`, inspected read-only at `/home/sfkim/projects/mcpbench/.worktrees/T009`. Review date: 2026-11-07. Source was frozen throughout. No P0/P1 defects observed. This is a static corpus gate, not runtime admission or application proof.

## Identity, scope and preservation — PASS

`git rev-parse HEAD` returned the exact candidate above; `git status --porcelain` returned the empty string before and after checks. `git diff --stat 7116a10 HEAD` showed exactly 11 files, 830 insertions, all within `eval/fixtures/**`. SHA-256 of every one of the 11 candidate source files matched `state/candidates/T009-v1.json` before/after testing. All four governance hashes matched their MAIN files; candidate worktree governance contains historical copies, so those MAIN hashes intentionally do not refer to worktree copies. This distinction was confirmed with the orchestrator. No contract source or governance was modified.

The test harnesses used existing Python dependencies, `PYTHONDONTWRITEBYTECODE=1`, deep copies and automatically cleaned `mcpbench-t009-independent-*` temporary directories. No candidate/source/test edits were made. The only persisted tester write is this report. No network, installation, database, Docker, model, build, host-resource probe or subagent was used.

## Actual commands and results

Commands below ran from the candidate worktree:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest contracts.tests.test_contracts eval.fixtures.test_fixtures -v
PYTHONDONTWRITEBYTECODE=1 python3 -m eval.fixtures.validate
PYTHONDONTWRITEBYTECODE=1 python3 -m contracts.validate Fixture eval/fixtures/v1/fixture.json
PYTHONDONTWRITEBYTECODE=1 python3 -m contracts.validate Task eval/fixtures/v1/tasks/smoke-invoice.json
PYTHONDONTWRITEBYTECODE=1 python3 -m contracts.validate Task eval/fixtures/v1/tasks/baseline-invoice.json
PYTHONDONTWRITEBYTECODE=1 python3 -m contracts.validate Task eval/fixtures/v1/tasks/baseline-project.json
PYTHONDONTWRITEBYTECODE=1 python3 -m contracts.validate Task eval/fixtures/v1/tasks/baseline-time.json
```

Observed: 46 tests ran in 2.388 seconds, `OK` (32 contracts plus 14 fixtures). Corpus CLI exit 0:

```text
PASS: fictional-billing-dev (4 tasks); seed=8303fb14daf4ae93b75a9df9b2faa56ff9f28ab2d0c489689e9159ad848f9c78
```

Fixture CLI returned `VALID: Fixture`; each of four task CLIs returned `VALID: Task`, all exit 0.

Three independent inline Python invocations (`PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'`, exit 0 each) performed identity/hash checks, the 41-case semantic matrix plus literal/canonical oracle, then seven additional corruptions plus repeatability/final identity checks. The semantic harness copied `eval.fixtures.validate.ROOT` for every case, mutated JSON via `contracts.validate.load_file`, recomputed the fixture's canonical `seed_hash`, synchronized `manifest.seed_hash`, SHA-256 rehashed all existing registered files, then invoked `validate_corpus(temp_root)`. Every case raised `ContractError`; unexpected acceptance raised `AssertionError`. The exact independent operations and observed rejection categories are recorded below, making clear which checks were not masked by hash mismatches.

## Criterion mapping and independent negative evidence

| Criterion | Result | Independent observed evidence |
| --- | --- | --- |
| Pinned fixture/data/task identity and versions | PASS | Fixture schema 2 rejected (`schema violation in Fixture`); fixture/migration version 2 rejected (`fixture version/identity`); task version 2 rejected (`task version/split`); manifest schema/dataset version 2 rejected (`manifest version/split`). |
| Catalog/schema pinning | PASS | Manifest catalog version 2 and schema SHA-256 zeroes rejected (`stale contract hashes/version`); actual schema/catalog bytes match registered hashes. |
| Canonical reproducibility | PASS | Independent sorted-table, compact sorted-key UTF-8 JSON SHA-256 equals the frozen fingerprint. Reversed every table's row order, rehashed fixture bytes, and corpus result still equaled two repeated original corpus results. |
| Fixture completeness and references | PASS | Duplicate item key rejected (`duplicate table key`); removed customer and broken project customer rejected (`project customer missing`); broken timesheet project/item rejected (`timesheet reference missing`). |
| Active targets and meaningful price decoys | PASS | Inactive target customer/decoy item rejected (`inactive target or decoy`); target price 12600 and decoy price 12500 rejected (`independent seed prices`). Two active fictional customers/items/projects and two same-date timesheets have distinct IDs and different customer/project/item relationships. |
| Independent fixed invoice oracle | PASS | Checked literal customer CUST-001, SVC-CONSULT quantity 2 at 12500 cents, dates 2026-11-07/2026-11-21, USD, subtotal/total 25000 and tax 0 in both invoice tasks. Verified independent integer arithmetic 12500 × 2 = 25000. Wrong customer/date/due date rejected (`independent invoice specification`); total 25001 rejected (`expected-state arithmetic mismatch`); tax 1 rejected (`schema violation in Task`). Coordinated seed price 12600 plus both tasks' matching price and subtotal/total 25200 still rejected (`independent seed prices`). |
| Dates and strict types | PASS | Impossible timesheet date 2026-11-31 and boolean minutes rejected (`schema violation in Fixture`). Valid but wrong target date 2026-11-07 rejected (`read oracle predicate mismatch`). |
| Read oracle existence and exact IDs | PASS | Missing project PRJ-404 rejected (`read expected record missing from fixture`); decoy timesheet TS-2E9A rejected (`read oracle predicate mismatch`). Natural predicates uniquely select PRJ-7F3A and TS-8B4D in the actual seed. |
| Natural prompts without ID echo | PASS | Actual public read prompts/task IDs do not contain private answer IDs. Appending PRJ-7F3A to project prompt rejected (`read prompt specification`); inserting it into task ID rejected (`missing or duplicate task`). |
| Full authorized exposure | PASS | Smoke exposes exactly three tools; baseline invoice all ten drafter tools; both reader tasks all nine reads. Replacing baseline invoice/time permitted tools with relevance subsets rejected (`full authorized catalog required`); granting reader draft creation rejected (`reader task includes draft permission`); drafter identity for project task rejected (`principal mismatch`). |
| Required/relevant annotations | PASS | Invoice create individually required, lists optional relevant. Read required sets empty, avoiding false claims about unique discovery paths; substituting required timesheet-list rejected (`conservative read required set`). README explicitly records alternate paths and T026 relevance review; no held-out tuning or winner claim. |
| Development-only corpus | PASS | All four actual tasks development; held-out mutation rejected (`schema violation in Task`). Manifest split and task roles pinned. |
| Declarative original/unchanged/replay data | PASS | Assertion data matches literal specification: one draft/header/line/idempotency addition; unchanged customers/items/projects/timesheets; same-ID replay, conflict for changed quantity, unchanged final application state, no replay repair; read-only exact IDs/unchanged state/successful authorized read trace/zero verifier calls. Replacing invoice assertions with replay permitting creation rejected (`assertion specification changed`). These are data, not executed grader assertions. |
| Manifest inventory/path safety | PASS | Extra `../escape.json` and `/tmp/outside.json` manifest entries rejected (`manifest file inventory`); extra JSON rejected (`unregistered corpus JSON`); wrong task role rejected (`task role inventory`). Registered fixture file symlink rejected (`invalid corpus file`); tasks-directory symlink rejected (`unregistered corpus JSON`). |
| Missing/duplicate and stale bytes | PASS | Removing project task rejected (`unregistered corpus JSON`); replacing project task with time task and rehashing rejected (`missing or duplicate task`). Duplicate JSON schema_version key with matching file hash rejected (`duplicate JSON object key`). Appending fixture whitespace without updating its hash rejected (`stale file hash`); zeroed manifest seed hash rejected (`seed fingerprint`). |
| CLI negative behavior | PASS | Ran `subprocess.run(['python3', '-m', 'eval.fixtures.validate', '--root', str(temp_root)], capture_output=True, text=True)` on stale-byte corpus under inherited disabled bytecode environment: exit 1, stdout exactly `FAIL: invalid static corpus`. |
| Implementation scope | PASS | Diff confined to fixture data, fixture validator, focused tests and fixture documentation; no early server, SQL, runner, grader, embeddings or retrieval implementation. |

Independent semantic matrix output ended `INDEPENDENT SEMANTIC MATRIX 41 REJECTED AS EXPECTED`; additional matrix ended `ADDITIONAL INDEPENDENT MATRIX 7 REJECTED AS EXPECTED`. Independent canonical digest was `8303fb14daf4ae93b75a9df9b2faa56ff9f28ab2d0c489689e9159ad848f9c78`; literal oracle/non-echo and row-order/repeatability checks passed. Final output confirmed `source_hashes 11 MATCH`, `governance_hashes 4 MATCH`, and `FINAL CANDIDATE CLEAN/FROZEN PASS`.

## Explicit limits and remaining gates

Runtime PostgreSQL migration/seed twice/reset fingerprints, independent database snapshot grading, settlement/revocation fences, successful authorized read trace, actual MCP permissions, idempotent replay/conflict execution, Docker and live model behavior: **UNRUN**. Static declarations cannot establish any of these. T001 model-storage access/resource admission remains **BLOCKED** as supplied; no bypass or host probe was attempted. These are later runtime prerequisites and do not fail this static T009 gate.

Overall tester verdict: **PASS** for the frozen T009 static deliverable. No observed P0/P1 defect; no source changes requested. Orchestrator owns integration and DAG status.
