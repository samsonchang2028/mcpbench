# T009 independent review

Verdict: **APPROVE**. No open P0/P1 findings.

Candidate: `f6b196e9c7f070d06256ae887198afa386f52330`, base `7116a10`, reviewed in
`/home/sfkim/projects/mcpbench/.worktrees/T009`. HEAD matched the frozen candidate;
working tree was clean before and after checks. The complete candidate diff is
11 files, 830 additions, exclusively `eval/fixtures/**`. This report is the only
reviewer write, in MAIN.

Read MAIN AGENTS.md, agents/reviewer.md, T009/reviewer context packs, task graph
row, evaluation plan, repo map, approved contract README/protocol and relevant
validator APIs; inspected every candidate fixture/task/assertion, validator,
test and README. Applied token-efficient-coding. T006 was not re-reviewed.

## Acceptance mapping

- Versioned synthetic corpus: one development fixture, four development tasks,
  two active customers/items/projects and two timesheets; empty initial invoice,
  line and idempotency tables. No held-out records, runner, server, SQL,
  selector, embeddings or premature grader implementation.
- Smoke literals preserved: CUST-001, SVC-CONSULT, quantity 2, unit price 12500,
  2026-11-07/2026-11-21, USD, tax 0, total 25000. Both invoice expected states
  contain independent literal expectations; validator checks those literals
  separately from contract arithmetic and seed agreement. Declarative private
  assertions cover one draft/line/idempotency write, unchanged seed tables,
  same-ID replay, conflict and prohibition on replay repair.
- Active decoys differ in customer ID/name, project ownership/name and item
  ID/price (17500); both same-date timesheets belong to different projects.
  Customer/project/item foreign keys agree. Exact read predicates resolve only
  PRJ-7F3A and TS-8B4D. Read prompts/task IDs do not contain those answer IDs.
  Read expectations specify the correct table, exact IDs, no changed tables and
  read_result_ids. No agent-only data projection exposes private expectations.
- Exposure is complete: smoke3 separately; baseline drafter has all ten tools;
  both baseline reader tasks have all nine read tools, including distractors.
  Only invoice creation is individually required. Empty read required sets and
  the conservative relevance sets accommodate alternative discovery paths;
  README explicitly records ambiguity and T026 review, without a winner claim.
- Dataset manifest pins data bytes, contract schema/catalog bytes and versions,
  seed hash, role inventory and development split. Independent serialization
  and SHA256 reproduced
  `8303fb14daf4ae93b75a9df9b2faa56ff9f28ab2d0c489689e9159ad848f9c78`.
  Row-order repeatability and run/control-metadata exclusion are tested.
- README/assertions explicitly require later successful authorized read trace
  evidence. SQL migration/seed/reset, replay, fences, authorization, live model
  behavior and runtime mount isolation are UNRUN, not inferred from static tests.
  T001 remains binding; this approval does not admit runtime operations.

## Actual checks

All commands ran from the candidate root; Python used
`PYTHONDONTWRITEBYTECODE=1`. No network, packages, DB, Docker, inference, builds,
host probes or subagents were used.

| Command/check | Actual result |
| --- | --- |
| `git rev-parse HEAD` | Frozen candidate SHA above |
| `git diff --stat 7116a10..HEAD -- eval/fixtures` | 11 files / 830 additions |
| `git diff --name-only 7116a10..HEAD` | Only authorized fixture lane |
| `git status --short` / `git status --porcelain` | Empty before/after |
| `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest contracts.tests.test_contracts eval.fixtures.test_fixtures -q` | 46 tests, OK, 2.385s |
| `PYTHONDONTWRITEBYTECODE=1 python3 -m eval.fixtures.validate` | PASS, four tasks, pinned seed hash |
| `PYTHONDONTWRITEBYTECODE=1 python3 -m contracts.validate Fixture eval/fixtures/v1/fixture.json` | VALID: Fixture |
| `PYTHONDONTWRITEBYTECODE=1 python3 -m contracts.validate Task eval/fixtures/v1/tasks/smoke-invoice.json` | VALID: Task |
| Independent `PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'` checks using deep copies and `TemporaryDirectory(prefix='mcpbench-t009-review-')` | PASS checks below; exit 0 |

Independent checks did not simply rerun author tests: loaded frozen records via
the strict loader, deep-copied and mutated them, recomputed the fixture seed hash
before semantic validation, and required ContractError for each of 18 cases:
duplicate customer; broken project/customer and timesheet/item FKs; changed fixed
price; inactive customer; wrong expected customer/date/total; missing and wrong
existing read targets; changed timesheet date predicate; boolean minutes;
answer-ID prompt echo; reader write permission; baseline relevant-only prefilter;
fixture version; held-out split; and permission for replay repair.

Five independent temporary corpus probes also rejected stale file bytes, stale
catalog version, manifest traversal entry, leaf symlink and changed invoice due
date. The due-date file hash was recomputed in the manifest before validation,
so its rejection proves semantic checking rather than a stale-hash shortcut.
The script also independently sorted all seven tables by their primary keys,
serialized the specified version/tenant/tables object using compact sorted JSON,
and recomputed SHA256 without calling seed_hash; it matched. Direct approved
Fixture and all four Task validation calls passed.

All 11 source hashes and four MAIN governance hashes from T009-v1.json matched
before the independent probes and again after all checks. An initial hash-check
invocation exited on AGENTS.md because it compared the MAIN governance pins
against the older worktree copies; it performed no mutation probes. The corrected
check used MAIN, as directed by the review context. Worktree governance has no
candidate changes relative to base. This is an evidence-location distinction,
not a candidate defect.

## Residual limits

Static approval proves corpus consistency and bounded local validation only.
Actual read evidence, server-authoritative billing, database oracle correctness,
reset/replay behavior and runtime isolation remain later DAG gates. Required/read
relevance annotation choices remain explicitly provisional for T026; no retrieval
quality or model success is claimed. There are no missing static T009 acceptance
checks that block this candidate.
