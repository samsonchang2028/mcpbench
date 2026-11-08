# MCPBench v1 contracts

T006 candidate: a contract bundle and offline validator, not an MCP server,
database, agent or observed benchmark. No grant, runtime operation or live model
call has been performed by this task. The approved behavior lives in
[architecture](../docs/ARCHITECTURE.md), [evaluation](../docs/EVALUATION_PLAN.md),
and [security/resource rules](../docs/SECURITY_RESOURCE_CONTRACT.md).

## Files and validation

- [Manifest](manifest.json) pins the schema and catalog bytes with SHA-256.
- [Schema](v1/schema.json) uses Draft 2020-12 and named definitions for data,
  tools, fixtures, requests/results, JSONL events, grading and private control data.
- [Catalog](v1/catalog.json) fixes all ten tools and their input/output references;
  its first three tools form the invoice smoke slice.
- [Examples and negative cases](v1/cases.json) are synthetic contract tests, not
  results. Separate example files show the same major wire objects. They contain
  no usable capability or DB secret. Full task/seed fixture sets remain T009 work.
- [Protocol](PROTOCOL.md) freezes launch transport, privileges, settlement, hashes,
  pagination, retries and error handling that schemas alone cannot establish.

Run from the repository/worktree root with the already installed dependencies:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest contracts.tests.test_contracts -v
PYTHONDONTWRITEBYTECODE=1 python3 -m contracts.validate Catalog contracts/v1/catalog.json
PYTHONDONTWRITEBYTECODE=1 python3 -m contracts.validate Task contracts/v1/task.example.json
PYTHONDONTWRITEBYTECODE=1 python3 -m contracts.validate ControlChain contracts/v1/control-chain.example.json
PYTHONDONTWRITEBYTECODE=1 python3 -m contracts.validate ControlChain contracts/v1/read-control-chain.example.json
PYTHONDONTWRITEBYTECODE=1 python3 -m contracts.validate ControlChain contracts/v1/failed-control-chain.example.json
PYTHONDONTWRITEBYTECODE=1 python3 -m contracts.validate EventStream contracts/v1/interrupted-trace.example.json
```

[requirements.txt](requirements.txt) records the exact installed validator dependency
versions used for T006; this task installs nothing. Python 3.14.4 was used. T008
will integrate these requirements with the application's pinned environment.

Use `load_bytes`/`load_file` and `validate`, not a shape-only JSON Schema call.
The loader rejects duplicate keys, non-finite values, invalid UTF-8, excessive
nesting and documents over 1 MiB. Integers are strict lexical JSON integers:
`2` is accepted; `2.0`, exponent forms for integer fields, booleans and strings are
not normalized into an integer. Dates and UTC timestamps are explicitly asserted,
including rejecting 24:00, impossible dates, timezone offsets and leap seconds.
All schema references resolve inside the bundle; network retrieval is disabled.

`validate_task_fixture` checks the task/fixture identity and canonical expected
prices against the independently seeded items. `seed_hash`, `payload_hash` and
`schema_name` implement the frozen canonical/identifier rules. Validation failures
raise `ContractError` with a bounded category, without echoing argument values.

The manifest registers every standalone example and its named contract; the tests
validate the entire registry. `ControlChain` cross-validates phase messages, host
exit/delivery records, verifier scope and one shared post-agent budget. `Event`
requires evidence specific to its operation; `EventStream` checks a complete trace's
sequence, identities and operation closure. Its example is a JSON array for offline
validation; production transport remains one individually bounded Event per JSONL
line. A single Event does not prove stream completeness.

Use `validate_run_bundle(task, fixture, mapping, evaluation, agent_result)` to bind
the private workflow kind and hashes to the actual task and agent answer. Read-only
expected records name their table and must exist in the seed; successful answers
contain the exact expected ID set. Grader data stays outside AgentRequest. Successful
read-only evaluation uses the acknowledged initial fence and unchanged final state,
with no verifier capability or calls. The draft-invoice gate still requires both
verifier checks and both fences. Settled, fully observed agent failures remain
eligible measured comparisons; unsafe settlement/evidence/verification cannot.

## Contract boundary

Every top-level wire object has `schema_version: 1`. Nested SQL/domain rows use
their containing object's version and the migration version. Unknown fields,
versions and unregistered tools fail closed. The bundle currently registers the
ten baseline tools; later T026/T028 catalog extensions must register their safe
executable schemas and freeze a new schema/catalog hash before any larger catalog
is exposed. No tool is accepted merely because a retrieval index returns its name.

Schema-valid data does not prove authentication, safe mounts, database locking,
resource admission, original state correctness or observed model support. Those
require T018–T023/T040 evidence. The example `FenceReceipt` is deliberately not an
observed transaction receipt. No schema test can authorize reset of uncertain live
state, create a missing invoice through replay, or turn metadata into live success.

All four strategy IDs are reserved: `full_context`, `semantic_top_k`, `hybrid`,
`hierarchical`. This freeze implements no selector. Ranking, embedding, k, fusion,
hierarchy and held-out campaign settings remain T026/T039 decisions. V1 uses JSONL
and durable artifacts only; OpenTelemetry, Jaeger and dashboard are outside v1.
