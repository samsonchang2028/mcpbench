# T008 independent reviewer

Candidate: `faaadeb2b42f4005e467e2064bdc1c766b409291` in `.worktrees/T008`, compared with `c258e09`.
Verdict: **APPROVE** for the T008 scaffold/dependency-selection scope. No P0/P1 findings.

## Findings

None. All 25 changed paths are within the assigned implementation ownership. The inspected candidate is clean and fixed at the revision above. There is no change to `contracts/` or `eval/fixtures/`.

## Inspected evidence

- Reviewed the complete candidate diff, Go module/checksum files, Python project/full distribution lock, image lock, Makefile, entrypoints, package boundaries and dependency/README claims against the T008 context pack, task row, architecture, component protocol and evaluation-first rules.
- Cached pinned official SDK `github.com/modelcontextprotocol/go-sdk@v1.8.0/mcp/shared.go` explicitly selects `2026-07-28` as the latest/client/default-server protocol, with exactly the four older supported versions listed in `docs/DEPENDENCIES.md`. Its compatibility table agrees. SDK and pgx v5.11.0 module sources require Go 1.25.0; selected Go 1.26.8 satisfies both. This is source evidence of supported selection, not exercised negotiation.
- Go direct/indirect requirements and checksums are explicit. Build-tagged reservation imports retain and compile-check the selected libraries without importing them into the ordinary fail-closed commands. Python preserves all five exact frozen validator versions and adds only psycopg 3.3.8 and its matching binary distribution. The lock contains distribution hashes and CPython 3.14 Linux/x86_64 wheel entries; the documented portability limit is accurate.
- The four image references are official `docker.io/library` names with separate index, linux/amd64 manifest and config identities. Deployment references pin the platform manifest digest. Image identity is explicitly distinguished from future build/runtime/non-root compatibility proof. Independent remote registry metadata validation belongs to the tester report; this review did not fetch images or registry content.
- Go agent/server and Python evaluator source writes only a fixed stderr message and returns 2. It reads no arguments, files or credentials, creates no result artifact, opens no listener and performs no billing, database, MCP or Ollama operation. Empty boundaries contain no migration, selector, telemetry framework or executable application implementation.
- Makefile enforces exact installed Go/Python/uv versions, disables automatic Go/Python toolchain downloads, installs Python wheels with `--no-build`, preserves locked resolution and limits Go parallelism. Setup/compilation explicitly require refreshed admission; no target starts containers, changes services or invokes inference. Offline Python checks and deterministic fixtures remain separate from future live-model checks.
- Recorded admission evidence exists in the main checkout. Its bytes hash to `c3459f7951fab77d42cc60311b61a4e3dcacaa9404856533ec29277bf003cb4e`, matching `state/audits/2026-11-08-T008-admission.json`; that record limits admission to bounded T008 dependency work. No new host operation was required for this read-only review.
- README/dependency documentation consistently labels the current commands as scaffold failures and leaves DB/MCP/evaluator/model behavior and image deployment UNRUN. It makes no invoice-success, runtime-security or comparative-strategy claim.

## Required independent evidence and limits

The tester separately owns actual locked-environment checks, 46 existing tests, fixture CLI, compilation/vet, lock consistency, subprocess behavior and official registry identity verification. The tester reported offline `make check`, tidy-diff, the 46 tests/fixture CLI and nine fail-closed invocations passing while this review was in progress; its final report is the authoritative independent execution record. Root must require that report's PASS and complete image metadata evidence before integration/T008 completion. Reviewer did not rerun those checks or perform installs, builds, image pulls, startup or inference.

No contract drift or unresolved review finding was identified. Future transport/authentication, server-authoritative billing, transactions/idempotency, database-driver compatibility, container runtime libraries/non-root setup, independent grading/reset and live model behavior remain their own DAG gates. Approval does not authorize workload startup, deployment or task completion.
