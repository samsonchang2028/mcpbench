# T009 development corpus, version 1

This is one synthetic seed and four development tasks under the approved T006
contract bundle. It contains no held-out records, runtime results, evaluator,
selector, database connector or model settings. The seed fingerprint is
`8303fb14daf4ae93b75a9df9b2faa56ff9f28ab2d0c489689e9159ad848f9c78`.

From the repository/worktree root, using existing dependencies:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m eval.fixtures.validate
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest eval.fixtures.test_fixtures -v
PYTHONDONTWRITEBYTECODE=1 python3 -m contracts.validate Fixture eval/fixtures/v1/fixture.json
PYTHONDONTWRITEBYTECODE=1 python3 -m contracts.validate Task eval/fixtures/v1/tasks/smoke-invoice.json
```

The CLI is read-only, returns nonzero for invalid data, and accepts `--root` for a
separate corpus directory. `v1/manifest.json` pins exact data bytes, schema/catalog
bytes and versions, roles, split and the canonical seed hash. Its inventory is
closed to unregistered JSON files. No automatic hash repair is provided: a dataset
change requires conscious review and versioning. Python source and this README
are revision-controlled, not included in the data manifest. Canonical business
fingerprinting uses the approved helper: row order does not matter; fixture and
migration versions, tenant and all seven business tables do. Generated run/control
metadata is excluded by the hash helper and forbidden inside a Fixture record.

| Task | Principal | Exposed tools | Expected outcome |
| --- | --- | --- | --- |
| smoke-invoice | billing-drafter | smoke3 | One USD draft, 25000 cents |
| baseline-invoice | billing-drafter | all baseline10 | Same invoice specification |
| baseline-project | billing-reader | all nine reads | Exact matching project ID |
| baseline-time | billing-reader | all nine reads | Exact matching timesheet ID |

The smoke prompt and literals are unchanged: CUST-001, two hours of SVC-CONSULT,
12500 cents/hour, 2026-11-07 dated, 2026-11-21 due, zero tax and 25000 cents total.
`Task.expected_state` holds literal invoice expectations independent of server
code and seed-derived arithmetic. Static checks separately verify seed agreement,
contract arithmetic, dates, IDs and original specification. `assertions.json`
records additional future original-state, unchanged-seed, replay/conflict and
read-only obligations. Those are declarative acceptance data, not executed
assertions or a snapshot grader. Dynamic invoice/line/idempotency IDs and creation
timestamps are intentionally unspecified; later grading must verify saved-ID
relationships and valid generated fields rather than expect fixed runtime IDs.

All seed write tables start empty. Both customers, items and projects are active.
Similar customer/project names, different item prices, and same-date timesheets
for different projects make wrong IDs, prices and insufficient filtering visible.
Read prompts use names/date predicates; opaque answer IDs appear only in private
seed/oracle data. Later launchers must mount only sanitized requests for agents,
never this directory, the manifest or assertions.

## Annotation choices and T026 follow-up

`permitted_tools` always includes the complete authorized catalog for its role;
it is never filtered to the known answer path. Full context must face distractors.
Only create-draft is individually required for invoice tasks. Customer/item lists
are optional relevant checks; baseline customer-get is also relevant. Invoice-get
and invoice-list could support self-verification but are excluded from this
minimal relevance annotation because the create result already returns the saved
draft. T026 must explicitly review whether verification utility broadens relevance.

Read tasks have empty individually required sets, so required-tool recall is
undefined/null under T006. This deliberately avoids asserting one mandatory path:
projects can be listed directly, or project IDs discovered from timesheets and
then fetched. Customer lookup/get can disambiguate ownership. Time records can be
listed with customer/project/date filters, or listed broadly then joined with
project/customer reads and optionally fetched individually. Listings need client
filtering for names and billability, which are not catalog input filters. Empty
required sets do not mean no reads are needed. Relevant sets conservatively cover
these useful discovery/confirmation paths. Guessed opaque IDs and gratuitous
reads are not the basis of annotation. Relevance is strategy-neutral but these
borderline choices and alternate paths need T026 annotation review before any
retrieval campaign freeze; no ranking/k/held-out tuning has occurred here.

Later T010/T019 read grading must require actual successful authorized read trace
evidence, the exact answer ID set, and unchanged settled application state. Agent
call-count claims or preknown IDs alone are insufficient. This corpus proves only
static consistency. PostgreSQL migration/seed/reset, runtime authorization, both
settlement fences, replay/conflict execution and live model behavior are UNRUN.
The T001 resource/access blocker remains binding for runtime admission.
